"""
Genera preguntas orales a partir de átomos usando Llama 4 Scout.
"""

import asyncio

from groq import Groq

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

groq_client = Groq(api_key=settings.groq_api_key)

# Cache de preguntas generadas por átomo (evita regenerar en repetir/reanudar)
_question_cache: dict[str, str] = {}


_LANG_INSTRUCTION = {
    "es": "Responde SIEMPRE en español.",
    "en": "ALWAYS respond in English.",
    "de": "Antworte IMMER auf Deutsch.",
}

PROMPT_PREGUNTA = """You are a teacher creating oral comprehension questions.
Generate ONE short, clear question about the given concept.
The question must be answerable in 1-3 spoken sentences.
Return ONLY the question, no prefixes or explanations.
{lang_instruction}"""

PROMPT_PISTA = """You are a tutor. The student asked for a hint.
Give a hint in 1-2 short sentences (max 30 words). NEVER give the full answer directly.
Use ONE of these techniques:
1) Fill-in-the-blank: give the first words of the answer followed by "..."
2) Contrast: "Think about the opposite of [X]..."
3) Context: give a related fact that guides toward the answer.
4) Category: indicate which category or group the concept belongs to.
Return ONLY the hint, no explanations or prefixes.
{lang_instruction}"""


async def generar_pregunta(atomo_texto: str, titulo_corto: str, lang: str = "es") -> str:
    """Genera una pregunta oral para un átomo de conocimiento."""
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    prompt = PROMPT_PREGUNTA.format(lang_instruction=lang_instr)

    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Concept: {titulo_corto}\n\nExplanation: {atomo_texto}",
                },
            ],
            temperature=0.7,
            max_tokens=80,
        )

    response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=10.0)
    pregunta = response.choices[0].message.content.strip()
    logger.info(f"Pregunta generada [{lang}]: '{pregunta}'")
    return pregunta


async def generar_pregunta_cached(atomo_id: str, atomo_texto: str, titulo_corto: str, lang: str = "es") -> str:
    """Genera pregunta con cache por atomo_id + lang. Reutiliza si ya se generó."""
    cache_key = f"{atomo_id}_{lang}"
    if cache_key in _question_cache:
        logger.info(f"Pregunta cache HIT para átomo {atomo_id[:8]} [{lang}]...")
        return _question_cache[cache_key]
    pregunta = await generar_pregunta(atomo_texto, titulo_corto, lang=lang)
    _question_cache[cache_key] = pregunta
    return pregunta


async def generar_pista(atomo_texto: str, pregunta: str, lang: str = "es") -> str:
    """Genera una pista sin revelar la respuesta completa."""
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    prompt = PROMPT_PISTA.format(lang_instruction=lang_instr)

    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Question: {pregunta}\n\nCorrect answer (do not reveal completely): {atomo_texto}",
                },
            ],
            temperature=0.6,
            max_tokens=120,
        )

    response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=10.0)
    pista = response.choices[0].message.content.strip()
    logger.info(f"Pista generada [{lang}]: '{pista}'")
    return pista
