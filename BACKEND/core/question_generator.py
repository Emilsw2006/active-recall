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
    "es": "IDIOMA OBLIGATORIO: español. ESCRIBE ÚNICAMENTE EN ESPAÑOL. Aunque el concepto esté en otro idioma, tu respuesta debe ser 100% en español.",
    "en": "MANDATORY LANGUAGE: English. WRITE EXCLUSIVELY IN ENGLISH. Even if the concept text is in another language, your response must be 100% in English.",
    "de": "PFLICHTSPRACHE: Deutsch. SCHREIBE AUSSCHLIESSLICH AUF DEUTSCH. Auch wenn der Konzepttext in einer anderen Sprache ist, muss deine Antwort zu 100% auf Deutsch sein.",
}

PROMPT_PREGUNTA = """{lang_instruction}

You are a teacher creating oral comprehension questions.
Generate ONE short, clear question about the given concept.
The question must be answerable in 1-3 spoken sentences.
Return ONLY the question text, no prefixes or explanations."""

PROMPT_PISTA = """{lang_instruction}

You are a tutor. The student asked for a hint.
Give a hint in 1-2 short sentences (max 30 words). NEVER give the full answer directly.
Use ONE of these techniques:
1) Fill-in-the-blank: give the first words of the answer followed by "..."
2) Contrast: "Think about the opposite of [X]..."
3) Context: give a related fact that guides toward the answer.
Return ONLY the hint text, no explanations or prefixes."""


async def generar_pregunta(atomo_texto: str, titulo_corto: str, lang: str = "es") -> str:
    """Genera una pregunta oral para un átomo de conocimiento."""
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    prompt = PROMPT_PREGUNTA.format(lang_instruction=lang_instr)

    lang_names = {"es": "Spanish", "en": "English", "de": "German"}
    lang_name = lang_names.get(lang, "Spanish")

    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"[WRITE YOUR RESPONSE IN {lang_name.upper()} ONLY]\n\n"
                        f"Concept: {titulo_corto}\n\nExplanation: {atomo_texto}"
                    ),
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

    lang_names = {"es": "Spanish", "en": "English", "de": "German"}
    lang_name = lang_names.get(lang, "Spanish")

    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"[WRITE YOUR RESPONSE IN {lang_name.upper()} ONLY]\n\n"
                        f"Question: {pregunta}\n\nCorrect answer (do not reveal completely): {atomo_texto}"
                    ),
                },
            ],
            temperature=0.6,
            max_tokens=120,
        )

    response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=10.0)
    pista = response.choices[0].message.content.strip()
    logger.info(f"Pista generada [{lang}]: '{pista}'")
    return pista


_TITULO_LANG_NAME = {"es": "SPANISH", "en": "ENGLISH", "de": "GERMAN"}

_TITULO_SYSTEM = {
    "es": "Eres un generador de títulos. Tu única tarea: leer el texto y generar UN título de 4-6 palabras EN ESPAÑOL. Sin importar el idioma del texto de entrada, el título SIEMPRE en español. Solo el título, sin comillas ni puntuación.",
    "en": "You are a title generator. Your only task: read the text and generate ONE title of 4-6 words IN ENGLISH. Regardless of the language of the input text, the title MUST always be in English. Output only the title, no quotes, no punctuation.",
    "de": "Du bist ein Titel-Generator. Deine einzige Aufgabe: den Text lesen und EINEN Titel mit 4-6 Wörtern AUF DEUTSCH generieren. Egal in welcher Sprache der Eingabetext ist, der Titel MUSS immer auf Deutsch sein. Nur den Titel ausgeben, keine Anführungszeichen, keine Satzzeichen.",
}


async def generar_titulo_sesion(textos: list, lang: str = "es") -> str:
    """Genera un título descriptivo corto para una sesión a partir de los textos de sus átomos."""
    snippet = " | ".join(t[:200] for t in textos[:4] if t)
    if not snippet:
        return ""

    system_prompt = _TITULO_SYSTEM.get(lang, _TITULO_SYSTEM["en"])
    lang_name = _TITULO_LANG_NAME.get(lang, "ENGLISH")

    def _call():
        return groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"[RESPOND IN {lang_name} ONLY]\n\n{snippet}"},
            ],
            max_tokens=25,
            temperature=0.4,
        )

    try:
        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=6.0)
        titulo = response.choices[0].message.content.strip().strip('"\'').rstrip(".")
        logger.info(f"Título sesión generado [{lang}]: '{titulo}'")
        return titulo
    except Exception as e:
        logger.warning(f"Error generando título sesión: {e}")
        return ""
