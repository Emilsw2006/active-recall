"""
Genera preguntas de tipo test con Groq (rápido) + Gemini como fallback.
Produce preguntas con 0, 1 o 2 respuestas correctas para evaluar comprensión real.
"""

import asyncio
import json
import traceback

from groq import Groq

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_groq = Groq(api_key=settings.groq_api_key)

_LANG_INSTRUCTION = {
    "es": "IDIOMA OBLIGATORIO: español. Escribe TODO el JSON (preguntas, opciones, explicaciones) ÚNICAMENTE EN ESPAÑOL. Aunque los conceptos estén en otro idioma, el output debe ser 100% en español.",
    "en": "MANDATORY LANGUAGE: English. Write ALL JSON content (questions, options, explanations) EXCLUSIVELY IN ENGLISH. Even if the concepts are in another language, the output must be 100% in English.",
    "de": "PFLICHTSPRACHE: Deutsch. Schreibe ALLE JSON-Inhalte (Fragen, Optionen, Erklärungen) AUSSCHLIESSLICH AUF DEUTSCH. Auch wenn die Konzepte in einer anderen Sprache sind, muss der Output zu 100% auf Deutsch sein.",
}

PROMPT_TEST = """{lang_instruction}

You are an expert teacher creating a multiple-choice test to assess real understanding, not literal memorization.

Concepts to evaluate:
{conceptos}

Generate exactly {n} questions. Strict rules:

1. Each question has EXACTLY 4 options (A, B, C, D)
2. Vary the number of correct answers per question:
   - Type "una_correcta" (~50%): 1 correct option. Standard question.
   - Type "dos_correctas" (~30%): 2 correct options. Phrase as "Which of the following statements are CORRECT? (Select 2)"
   - Type "una_incorrecta" (~20%): 3 statements are true, 1 is false. Phrase as "Which of the following statements is INCORRECT?"
3. Incorrect options must be plausible (common conceptual errors, not obvious nonsense)
4. Cover different concepts in each question — don't repeat the same concept
5. For each option include a short explanation (1 line) of why it's correct or incorrect
6. The "explicacion" field summarizes the correct answer in a clear, educational way (2-3 lines)
7. In "correctas": indices (0-3) of the correct options. For "una_incorrecta" the index points to the FALSE option

Return ONLY valid JSON, no markdown, no extra text:
{{
  "preguntas": [
    {{
      "id": 0,
      "concepto_titulo": "title of the concept being evaluated",
      "pregunta": "full question text",
      "tipo": "una_correcta",
      "opciones": ["option A", "option B", "option C", "option D"],
      "correctas": [2],
      "explicacion": "Clear educational explanation of the correct answer (2-3 lines)",
      "explicaciones_opciones": [
        "A: Why it's correct or incorrect...",
        "B: Why it's correct or incorrect...",
        "C: Why it's correct or incorrect...",
        "D: Why it's correct or incorrect..."
      ]
    }}
  ]
}}""".strip()


def _parse_preguntas(raw: str) -> list[dict]:
    """Parse and validate JSON response into question list."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    data = json.loads(text)
    preguntas = data.get("preguntas", data) if isinstance(data, dict) else data

    validated = []
    for p in preguntas:
        if not all(k in p for k in ("pregunta", "tipo", "opciones", "correctas", "explicacion")):
            continue
        if len(p["opciones"]) != 4:
            continue
        if p["tipo"] not in ("una_correcta", "dos_correctas", "una_incorrecta"):
            p["tipo"] = "una_correcta"
        if "explicaciones_opciones" not in p or len(p["explicaciones_opciones"]) != 4:
            p["explicaciones_opciones"] = ["", "", "", ""]
        validated.append(p)
    return validated


async def generar_preguntas_test(atomos: list[dict], n: int = 5, lang: str = "es") -> list[dict]:
    """
    Genera preguntas de tipo test para una lista de átomos.
    Cada átomo: {id, titulo_corto, texto_completo}
    """
    conceptos_texto = "\n\n".join(
        f"[{i}] Título: {a['titulo_corto']}\nConcepto: {a['texto_completo'][:500]}"
        for i, a in enumerate(atomos)
    )

    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    prompt = PROMPT_TEST.format(conceptos=conceptos_texto, n=n, lang_instruction=lang_instr)

    # ── Groq (primary — fast) ────────────────────────────────────────────────
    def _groq_call():
        return _groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

    try:
        response = await asyncio.wait_for(asyncio.to_thread(_groq_call), timeout=30.0)
        preguntas = _parse_preguntas(response.choices[0].message.content)
        if preguntas:
            logger.info(f"Test generado con Groq — {len(preguntas)} preguntas [{lang}]")
            return preguntas
        logger.warning("Groq devolvió 0 preguntas válidas — intentando Gemini")
    except asyncio.TimeoutError:
        logger.warning("Groq timeout (30s) generando test — intentando Gemini")
    except Exception:
        logger.warning(f"Groq falló generando test:\n{traceback.format_exc()}")

    # ── Gemini fallback ──────────────────────────────────────────────────────
    try:
        import google.genai as genai
        from google.genai import types
        from core.limits import GEMINI_SEM

        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

        def _gemini_call():
            return client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.75,
                    response_mime_type="application/json",
                ),
            )

        async with GEMINI_SEM:
            response = await asyncio.wait_for(asyncio.to_thread(_gemini_call), timeout=45.0)

        preguntas = _parse_preguntas(response.text)
        if preguntas:
            logger.info(f"Test generado con Gemini fallback — {len(preguntas)} preguntas [{lang}]")
            return preguntas
    except asyncio.TimeoutError:
        logger.error("Gemini timeout (45s) generando test — sin preguntas")
    except Exception:
        logger.error(f"Gemini falló generando test:\n{traceback.format_exc()}")

    return []
