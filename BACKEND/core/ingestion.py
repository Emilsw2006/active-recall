"""
Procesa un PDF con Gemini 3 Pro (Vertex AI) y extrae temas → subtemas → átomos.
Guarda la estructura en Supabase y vectoriza los átomos.
"""

import json
from datetime import datetime

import google.genai as genai
from google.genai import types

from config import settings
from utils.logger import get_logger
from utils.supabase_client import get_service_client
from core.vectorizer import vectorize_atomos
from core.deduplicator import deduplicar_atomos

logger = get_logger(__name__)

# Gemini client: API key preferred, Vertex AI ADC as fallback
if settings.gemini_api_key:
    _client = genai.Client(api_key=settings.gemini_api_key)
else:
    _client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )

PROMPT_EXTRACCION = """
Analiza este documento y extrae su estructura completa de conocimiento.
Devuelve SOLO el siguiente JSON sin texto adicional, sin markdown, sin ```json:

{
  "temas": [
    {
      "titulo": "string",
      "orden": 1,
      "subtemas": [
        {
          "titulo": "string",
          "orden": 1,
          "atomos": [
            {
              "titulo_corto": "string (máx 60 caracteres)",
              "texto_completo": "string (explicación completa con todo el contexto necesario para entenderlo de forma independiente)",
              "orden": 1
            }
          ]
        }
      ]
    }
  ]
}

REGLAS CRÍTICAS:
- Cada átomo debe tener sentido completo por sí solo, sin depender de otros átomos.
- Cada átomo debe ser útil para generar una pregunta y evaluar la respuesta del estudiante.
- No hay límite artificial de palabras por átomo. Incluye todo el contexto necesario.
- No uses chunking por número de caracteres. Usa lógica semántica.
- Cubre TODO el contenido del documento sin omitir nada relevante.
""".strip()


async def procesar_pdf(
    pdf_bytes: bytes,
    documento_id: str,
    asignatura_id: str,
    usuario_id: str,
) -> None:
    """
    Background task: procesa el PDF completo y guarda en Supabase.
    Actualiza el estado del documento al terminar.
    """
    db = get_service_client()
    inicio = datetime.now()
    logger.info(f"[{documento_id}] Iniciando procesamiento PDF — {inicio.isoformat()}")

    try:
        # 1. Extraer estructura con Gemini
        logger.info(f"[{documento_id}] Enviando PDF a {settings.gemini_model}...")
        estructura = await _extraer_estructura_gemini(pdf_bytes, documento_id)
        # Defensive: ensure we always have a dict with 'temas' list
        if isinstance(estructura, list):
            logger.warning(f"[{documento_id}] _extraer retornó lista — normalizando en procesar_pdf")
            estructura = {"temas": estructura}
        if not isinstance(estructura, dict) or "temas" not in estructura:
            logger.error(f"[{documento_id}] Estructura inválida: {type(estructura).__name__}, keys={list(estructura.keys()) if isinstance(estructura, dict) else 'N/A'}")
            estructura = {"temas": []}
        logger.info(f"[{documento_id}] Gemini devolvió {len(estructura['temas'])} temas")

        # 2. Guardar en Supabase: temas → subtemas → átomos
        atomos_para_vectorizar = []

        for tema_data in estructura["temas"]:
            tema_res = (
                db.table("temas")
                .insert({
                    "documento_id": documento_id,
                    "titulo": tema_data["titulo"],
                    "orden": tema_data["orden"],
                })
                .execute()
            )
            tema_id = tema_res.data[0]["id"]
            logger.info(f"[{documento_id}] Tema: '{tema_data['titulo']}'")

            for subtema_data in tema_data.get("subtemas", []):
                subtema_res = (
                    db.table("subtemas")
                    .insert({
                        "tema_id": tema_id,
                        "titulo": subtema_data["titulo"],
                        "orden": subtema_data["orden"],
                    })
                    .execute()
                )
                subtema_id = subtema_res.data[0]["id"]

                for atomo_data in subtema_data.get("atomos", []):
                    atomo_res = (
                        db.table("atomos")
                        .insert({
                            "subtema_id": subtema_id,
                            "tema_id": tema_id,
                            "documento_id": documento_id,
                            "asignatura_id": asignatura_id,
                            "titulo_corto": atomo_data["titulo_corto"],
                            "texto_completo": atomo_data["texto_completo"],
                            "orden": atomo_data["orden"],
                        })
                        .execute()
                    )
                    atomos_para_vectorizar.append({
                        "id": atomo_res.data[0]["id"],
                        "texto_completo": atomo_data["texto_completo"],
                    })

        logger.info(f"[{documento_id}] {len(atomos_para_vectorizar)} átomos guardados. Vectorizando...")

        # 3. Vectorizar átomos (añade embedding en memoria a cada dict)
        await vectorize_atomos(atomos_para_vectorizar, documento_id)

        # 4. Deduplicar contra átomos de otros documentos de la misma asignatura
        dedup = await deduplicar_atomos(
            documento_id=documento_id,
            asignatura_id=asignatura_id,
            atomos_nuevos=atomos_para_vectorizar,
        )
        logger.info(f"[{documento_id}] Dedup: {dedup['nuevos']} únicos, {dedup['duplicados']} duplicados")

        # 5. Marcar documento como listo
        db.table("documentos").update({"estado": "listo"}).eq("id", documento_id).execute()

        duracion = (datetime.now() - inicio).total_seconds()
        logger.info(f"[{documento_id}] Completado en {duracion:.1f}s — {len(atomos_para_vectorizar)} átomos")

    except Exception as e:
        logger.error(f"[{documento_id}] Error: {e}", exc_info=True)
        db.table("documentos").update(
            {"estado": "error", "error_mensaje": str(e)}
        ).eq("id", documento_id).execute()


async def _extraer_estructura_gemini(pdf_bytes: bytes, documento_id: str) -> dict:
    """Llama a Gemini via Vertex AI con el PDF y devuelve el JSON parseado."""
    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            PROMPT_EXTRACCION,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    logger.info(f"[{documento_id}] Respuesta recibida ({len(raw)} caracteres)")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[{documento_id}] JSON inválido: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"Gemini devolvió JSON inválido: {e}")

    # Gemini sometimes returns a list instead of an object — normalise
    if isinstance(parsed, list):
        # Case 1: list of tema dicts (each has "titulo" + "subtemas")
        if parsed and isinstance(parsed[0], dict) and "subtemas" in parsed[0]:
            logger.warning(f"[{documento_id}] Gemini devolvió lista de temas directa — normalizando")
            return {"temas": parsed}
        # Case 2: list wrapping the whole object
        if parsed and isinstance(parsed[0], dict) and "temas" in parsed[0]:
            logger.warning(f"[{documento_id}] Gemini devolvió lista con objeto — extrayendo")
            return parsed[0]
        # Fallback: treat the whole list as temas
        logger.warning(f"[{documento_id}] Gemini devolvió lista desconocida — usando como temas")
        return {"temas": parsed}

    return parsed
