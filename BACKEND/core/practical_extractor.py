"""
practical_extractor.py
Extracts formulas, exercises, procedures and theory concepts from a PDF using Gemini.
Both theory (ingestion.py) and practical pipelines always run on every upload.

Content types (tipo_contenido):
  ejercicio    — Numerical problem with given data and step-by-step solution
  procedimiento — How-to / derivation / algorithm explained step by step (procedural theory)
  concepto      — Theory concept with embedded formulas and explanations

Block types (Server-Driven UI):
  TextBlock      { "type": "text",     "content": str }
  MathBlock      { "type": "math",     "latex": str }
  TableBlock     { "type": "table",    "headers": [], "rows": [[]] }
  ImageDescBlock { "type": "img_desc", "description": str }
  StepBlock      { "type": "step",     "n": int, "content": [Block] }
"""

import json
import logging

import google.genai as genai
from google.genai import types

from config import settings
from utils.supabase_client import get_service_client

logger = logging.getLogger(__name__)

# Reuse the same Gemini client strategy as ingestion.py
if settings.gemini_api_key:
    _client = genai.Client(api_key=settings.gemini_api_key)
else:
    _client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )

PROMPT_PRACTICO = """
Analiza este documento y extrae TODO el contenido estructurado: fórmulas, ejercicios resueltos,
procedimientos paso a paso y conceptos teóricos con fórmulas.

Devuelve SOLO el siguiente JSON sin texto adicional, sin markdown, sin ```json:

{
  "formulas": [
    {
      "nombre": "string — nombre corto de la fórmula",
      "latex": "string — LaTeX KaTeX-compatible SIN delimitadores $ ni $$",
      "tema": "string — tema del documento al que pertenece",
      "variables": [
        { "symbol": "string", "description": "string — qué representa y unidades" }
      ]
    }
  ],
  "contenidos": [
    {
      "tipo_contenido": "ejercicio | procedimiento | concepto",
      "tema": "string",
      "tipo": "string — subtipo temático (ej: cinemática, termodinámica, derivadas, etc.)",
      "titulo": "string — título corto descriptivo",
      "dificultad": 1,
      "dades": [
        { "symbol": "string", "value": "string", "unit": "string" }
      ],
      "enunciado": [
        { "type": "text | math | img_desc | table", "content": "...", "latex": "...", "description": "..." }
      ],
      "solucion": [
        {
          "type": "step",
          "n": 1,
          "content": [
            { "type": "text", "content": "string" },
            { "type": "math", "latex": "string SIN delimitadores $" }
          ]
        }
      ]
    }
  ]
}

TIPOS DE CONTENIDO — cuándo usar cada uno:
- "ejercicio"     → problema numérico con datos concretos (velocidad, masa, temperatura...)
                    y resultado calculable. Siempre tiene "dades" con valores.
- "procedimiento" → explica CÓMO hacer algo paso a paso sin datos numéricos concretos.
                    Ejemplos: derivar una fórmula, demostrar un teorema, algoritmo de resolución,
                    método de integración por partes, cómo aplicar el teorema de Bayes, etc.
                    "dades" estará vacío [].
- "concepto"      → explicación de qué ES algo, con fórmulas embebidas.
                    Ejemplos: qué es la entropía, definición de derivada, propiedades de los
                    vectores, qué es la impedancia. "dades" estará vacío [].

REGLAS CRÍTICAS:
- LaTeX: escribe SOLO el contenido, sin $ ni $$. Correcto: "F = ma". Incorrecto: "$F = ma$"
- Para imágenes o diagramas: { "type": "img_desc", "description": "descripción textual detallada" }
- dificultad: 1 (básico), 2 (intermedio), 3 (avanzado)
- Cubre TODO el documento. No omitas ningún ejercicio, procedimiento ni concepto relevante.
- Si el PDF es puramente teórico sin ejercicios numéricos, usa "procedimiento" y "concepto".
- Si no hay fórmulas aisladas, devuelve "formulas": []
- Si no hay contenidos, devuelve "contenidos": []
""".strip()


async def extract_practical_content(
    pdf_bytes: bytes,
    asignatura_id: str,
    documento_id: str,
) -> dict:
    """
    Calls Gemini to extract formulas + all content types from a PDF.
    Persists results to Supabase. Non-fatal: errors are logged, not raised.
    Returns counts per type on success.
    """
    logger.info(f"[practico/{documento_id}] Starting full content extraction...")

    try:
        data = await _call_gemini(pdf_bytes, documento_id)
    except Exception as e:
        logger.warning(f"[practico/{documento_id}] Gemini call failed: {e}")
        return {"formulas": 0, "ejercicios": 0, "procedimientos": 0, "conceptos": 0}

    formulas  = data.get("formulas",  []) or []
    contenidos = data.get("contenidos", []) or []

    # Backward compat: old key "ejercicios" still accepted
    if not contenidos:
        old = data.get("ejercicios", []) or []
        contenidos = [{**e, "tipo_contenido": "ejercicio"} for e in old]

    if not formulas and not contenidos:
        logger.info(f"[practico/{documento_id}] No content found — skipping persist")
        return {"formulas": 0, "ejercicios": 0, "procedimientos": 0, "conceptos": 0}

    db = get_service_client()

    # --- Persist formulas ---
    n_formulas = 0
    if formulas:
        formula_rows = [
            {
                "asignatura_id": asignatura_id,
                "documento_id":  documento_id,
                "tema":      f.get("tema", ""),
                "nombre":    f.get("nombre", ""),
                "latex":     f.get("latex", ""),
                "variables": f.get("variables", []),
            }
            for f in formulas
            if f.get("latex")
        ]
        if formula_rows:
            try:
                res = db.table("formulas_tema").insert(formula_rows).execute()
                n_formulas = len(res.data or formula_rows)
                logger.info(f"[practico/{documento_id}] Inserted {n_formulas} formulas")
            except Exception as e:
                logger.warning(f"[practico/{documento_id}] Formula insert error: {e}")

    # --- Persist contenidos ---
    counts = {"ejercicio": 0, "procedimiento": 0, "concepto": 0}
    if contenidos:
        rows = []
        for c in contenidos:
            if not c.get("enunciado") and not c.get("titulo"):
                continue  # skip empty entries
            tipo_contenido = c.get("tipo_contenido", "ejercicio")
            if tipo_contenido not in ("ejercicio", "procedimiento", "concepto"):
                tipo_contenido = "ejercicio"
            rows.append({
                "asignatura_id":  asignatura_id,
                "documento_id":   documento_id,
                "tema":           c.get("tema", ""),
                "tipo":           c.get("tipo", ""),
                "tipo_contenido": tipo_contenido,
                "titulo":         c.get("titulo", ""),
                "dificultad":     int(c.get("dificultad", 1)),
                "dades":          c.get("dades", []),
                "enunciado":      c.get("enunciado", []),
                "solucion":       c.get("solucion", []),
            })
        if rows:
            try:
                res = db.table("ejercicios").insert(rows).execute()
                inserted = res.data or rows
                for r in inserted:
                    tc = r.get("tipo_contenido", "ejercicio")
                    if tc in counts:
                        counts[tc] += 1
                logger.info(
                    f"[practico/{documento_id}] Inserted: "
                    f"{counts['ejercicio']} ejercicios, "
                    f"{counts['procedimiento']} procedimientos, "
                    f"{counts['concepto']} conceptos"
                )
            except Exception as e:
                logger.warning(f"[practico/{documento_id}] Content insert error: {e}")

    return {
        "formulas":       n_formulas,
        "ejercicios":     counts["ejercicio"],
        "procedimientos": counts["procedimiento"],
        "conceptos":      counts["concepto"],
    }


async def _call_gemini(pdf_bytes: bytes, documento_id: str) -> dict:
    """Sends PDF to Gemini and parses the JSON response."""
    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            PROMPT_PRACTICO,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    logger.info(f"[practico/{documento_id}] Gemini response {len(raw)} chars")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[practico/{documento_id}] JSON parse error: {e} — raw[:400]: {raw[:400]}")
        raise ValueError(f"Gemini returned invalid JSON: {e}")

    # Normalise: if Gemini wraps in a list
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}

    return parsed
