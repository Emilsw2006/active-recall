"""
Genera preguntas de tipo test con Gemini (Vertex AI).
Produce preguntas con 0, 1 o 2 respuestas correctas para evaluar comprensión real.
"""

import asyncio
import json

import google.genai as genai
from google.genai import types

from config import settings
from core.limits import GEMINI_SEM
from utils.logger import get_logger

logger = get_logger(__name__)

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

PROMPT_TEST = """You are an expert teacher creating a multiple-choice test to assess real understanding, not literal memorization.

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
7. In "correctas": indices (0-3) of the correct options. For "una_incorrecta" the index points to the FALSE option (which is the answer to "which is incorrect?")

{lang_instruction}

Exact JSON, no additional text:
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


async def generar_preguntas_test(atomos: list[dict], n: int = 5, lang: str = "es") -> list[dict]:
    """
    Genera preguntas de tipo test para una lista de átomos.
    Cada átomo: {id, titulo_corto, texto_completo}
    """
    # Truncate atom texts to avoid token limit issues
    conceptos_texto = "\n\n".join(
        f"[{i}] Título: {a['titulo_corto']}\nConcepto: {a['texto_completo'][:500]}"
        for i, a in enumerate(atomos)
    )

    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    prompt = PROMPT_TEST.format(conceptos=conceptos_texto, n=n, lang_instruction=lang_instr)

    def _call():
        return _client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.75,
                response_mime_type="application/json",
            ),
        )

    async with GEMINI_SEM:
        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=45.0)

    data = json.loads(response.text.strip())
    preguntas = data.get("preguntas", [])

    # Validate structure
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
