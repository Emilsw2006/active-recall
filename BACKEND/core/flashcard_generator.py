"""
Genera flashcards con analogías personalizadas usando Gemini.
Se invoca cuando la ruta de un átomo es 'rojo'.
Siempre regenera el contenido para que las analogías sean frescas y contextuales.
"""

import asyncio
import json
from datetime import datetime

import google.genai as genai
from google.genai import types

from config import settings
from core.limits import GEMINI_SEM
from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)

# Cliente Vertex AI (usa ADC — gcloud auth application-default login)
_client = genai.Client(
    vertexai=True,
    project=settings.google_cloud_project,
    location=settings.google_cloud_location,
)

_LANG_INSTRUCTION = {
    "es": "Responde SIEMPRE en español.",
    "en": "ALWAYS respond in English.",
    "de": "Antworte IMMER auf Deutsch.",
}

PROMPT_FLASHCARD = """
The student got this question wrong.

Context:
- Student interests (for analogies): {mundo_analogias}
- Incorrect answer given: "{respuesta_usuario}"
- Correct concept: {atomo_texto}

Generate a correction in 3 parts:

PART 1 — Why it's wrong: explicitly mention what the student said ("{respuesta_usuario}") and explain why it's incorrect. Be direct and specific (1-2 lines).

PART 2 — The correct answer: explain it clearly and completely (1-2 lines).

PART 3 — Analogy (MANDATORY — give a concrete example, do NOT ask the student to make one):
- Give ONE concrete analogy that explains the concept. Example: "It's like when..." or "Imagine..."
- NEVER say "practice", "review" or "try to make an analogy" — YOU provide the analogy.
- If "{mundo_analogias}" has a natural connection to the concept → use it
- If NOT → use an everyday analogy (cooking, sport, nature, daily life)
- 2-3 sentences. Complete and specific.

{lang_instruction}

Exact JSON, no additional text:
{{
  "paso_1_concepto_base": "✗ [quote student's answer]. That's incorrect because [specific reason — 1-2 lines]",
  "paso_2_error_cometido": "✓ [correct answer, complete]",
  "paso_3_analogia": "💡 [concrete analogy like 'It's like when...', 2-3 sentences]"
}}
""".strip()


async def generar_flashcard(
    atomo_id: str,
    usuario_id: str,
    atomo_texto: str,
    respuesta_usuario: str,
    mundo_analogias: str,
    lang: str = "es",
) -> dict:
    """
    Genera una flashcard para un átomo fallado.
    Siempre regenera el contenido (para analogías frescas con la respuesta incorrecta actual).
    Actualiza veces_fallada en DB si ya existe.
    """
    db = get_service_client()
    inicio = datetime.now()
    logger.info(f"Generando flashcard para átomo {atomo_id} (usuario {usuario_id})")

    mundo = mundo_analogias or "tecnología y ciencia"
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])

    # Generar contenido fresco con Gemini (siempre, para analogías contextuales)
    prompt = PROMPT_FLASHCARD.format(
        mundo_analogias=mundo,
        atomo_texto=atomo_texto,
        respuesta_usuario=respuesta_usuario,
        lang_instruction=lang_instr,
    )

    def _call_gemini():
        return _client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )

    try:
        async with GEMINI_SEM:
            response = await asyncio.wait_for(asyncio.to_thread(_call_gemini), timeout=15.0)
        pasos = json.loads(response.text.strip())
        # Validate all required fields are present and non-empty
        for key in ("paso_1_concepto_base", "paso_2_error_cometido", "paso_3_analogia"):
            if not pasos.get(key):
                raise ValueError(f"Missing field: {key}")
    except Exception as e:
        logger.error(f"Gemini flashcard error: {e}")
        # Fallback uses actual student response — builds a real comparison
        resp_preview = respuesta_usuario[:120] if respuesta_usuario else "(sin respuesta)"
        concepto_preview = atomo_texto[:150]
        pasos = {
            "paso_1_concepto_base": f"✗ Dijiste \"{resp_preview}\", pero eso no coincide con el concepto correcto. La diferencia clave es que {concepto_preview}",
            "paso_2_error_cometido": f"✓ Lo correcto es: {atomo_texto[:250]}",
            "paso_3_analogia": f"💡 Es como confundir la sal con el azúcar: parecen iguales a simple vista, pero el resultado es completamente distinto. Aquí lo que cambia todo es entender bien: {concepto_preview}",
        }

    # Check if flashcard already exists → upsert with fresh content
    existente = await asyncio.to_thread(
        lambda: db.table("flashcards")
        .select("id, veces_fallada")
        .eq("atomo_id", atomo_id)
        .eq("usuario_id", usuario_id)
        .execute()
    )

    if existente.data:
        fc_id = existente.data[0]["id"]
        veces = existente.data[0]["veces_fallada"] + 1
        updated = await asyncio.to_thread(
            lambda: db.table("flashcards").update({
                "paso_1_concepto_base": pasos["paso_1_concepto_base"],
                "paso_2_error_cometido": pasos["paso_2_error_cometido"],
                "paso_3_analogia": pasos["paso_3_analogia"],
                "veces_fallada": veces,
            }).eq("id", fc_id).execute()
        )
        flashcard = updated.data[0] if updated.data else {
            "id": fc_id,
            "atomo_id": atomo_id,
            "usuario_id": usuario_id,
            "veces_fallada": veces,
            **pasos,
        }
        logger.info(f"Flashcard actualizada (veces_fallada: {veces})")
    else:
        flashcard_data = {
            "atomo_id": atomo_id,
            "usuario_id": usuario_id,
            "paso_1_concepto_base": pasos["paso_1_concepto_base"],
            "paso_2_error_cometido": pasos["paso_2_error_cometido"],
            "paso_3_analogia": pasos["paso_3_analogia"],
            "veces_fallada": 1,
        }
        res = await asyncio.to_thread(lambda: db.table("flashcards").insert(flashcard_data).execute())
        flashcard = res.data[0]

    duracion = (datetime.now() - inicio).total_seconds()
    logger.info(f"Flashcard generada en {duracion:.1f}s para átomo {atomo_id}")

    return flashcard
