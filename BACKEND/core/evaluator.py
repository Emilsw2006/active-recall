"""
Evalúa la respuesta del usuario usando enfoque híbrido:
  - Similitud coseno muy alta (≥0.92) → verde directo (template, sin LLM)
  - Similitud coseno alta     (≥0.82) → verde con LLM praise
  - Resto                            → LLM evalúa con metodología Feynman/Active Recall

LLM devuelve {clasificacion: bien|medio|mal, accion, mensaje, detalle?}
  - bien  → verde
  - medio → amarillo (pide transformación sin dar respuesta)
  - mal   → rojo (4 bloques: error + micro-explicación + respuesta correcta + analogía)
"""

import asyncio
import json
from datetime import datetime
from typing import Tuple, Optional

import numpy as np
from groq import Groq

from config import settings
from core.limits import GROQ_LLM_SEM
from core.vectorizer import embed_texto
from utils.logger import get_logger

logger = get_logger(__name__)

groq_client = Groq(api_key=settings.groq_api_key)

# Umbrales para saltar el LLM en casos claramente correctos
UMBRAL_FAST_VERDE = 0.92   # Similitud muy alta → verde plantilla, sin LLM
UMBRAL_AUTO_VERDE = 0.82   # Similitud alta → verde con LLM praise

_LANG_INSTRUCTION = {
    "es": "IDIOMA OBLIGATORIO: español. Escribe ÚNICAMENTE en español.",
    "en": "MANDATORY LANGUAGE: English. Write EXCLUSIVELY in English.",
    "de": "PFLICHTSPRACHE: Deutsch. Schreibe AUSSCHLIESSLICH auf Deutsch.",
}

_LANG_FEEDBACK = {
    "es": {
        "fast_verde": "¡Perfecto! Lo tienes muy claro. Pasamos a la siguiente.",
        "pista_penalty": " (Has usado una pista, así que lo anotamos como amarillo.)",
    },
    "en": {
        "fast_verde": "Perfect! You've got it down. Moving on to the next one.",
        "pista_penalty": " (You used a hint, so we'll mark this as partial.)",
    },
    "de": {
        "fast_verde": "Perfekt! Das hast du sehr gut verstanden. Weiter zur nächsten Frage.",
        "pista_penalty": " (Du hast einen Hinweis benutzt, daher markieren wir dies als teilweise richtig.)",
    },
}

PROMPT_SISTEMA = """{lang_instruction}

You are an expert tutor applying the Feynman Technique and Active Recall.
Mission: detect REAL understanding, not surface recall or memorization.

{segundo_intento_note}

=== CLASSIFICATION — choose exactly one ===

BIEN — student genuinely understands:
  • Explains in their OWN words (not a copy of the source text)
  • Can explain WHY, not just WHAT
  • Another person could understand it from this explanation
  • May include a personal example or simplification

MEDIO — right direction, but understanding is shallow:
  • Too vague ("it affects things", "it has consequences", "it's important")
  • Sounds memorized — recites phrases without showing understanding
  • States WHAT but cannot explain WHY
  • Missing concrete example or analogy when needed
  • Disorganized or self-contradictory
  → Do NOT reveal the answer. Only ask for a specific transformation.

MAL — wrong, empty, or fundamentally incomplete:
  • Incorrect concept or major factual error
  • Misses the main point entirely
  • Just rephrases the question or gives irrelevant answer
  • Answer is empty or "I don't know"

=== OUTPUT: strict JSON only, no extra text ===

If BIEN:
{{"clasificacion": "bien", "accion": "confirmar", "mensaje": "2-3 warm sentences. Mention specifically what they got right. Genuine, not hollow."}}

If MEDIO — pick the ONE transformation targeting the exact weakness. No hints:
  Vague          → ask them to explain it to a 10-year-old using simple words
  No WHY         → ask them to explain WHY it happens, not just what it is
  No example     → ask for one specific real-life example
  Memorized      → ask them to rephrase in completely different words
  Disorganized   → ask them to explain step by step, one idea at a time
{{"clasificacion": "medio", "accion": "transformar", "mensaje": "One direct sentence requesting the specific transformation. No hints about content."}}

If MAL:
{{
  "clasificacion": "mal",
  "accion": "corregir",
  "mensaje": "2 spoken sentences. Kindly name what was wrong. Natural language, no markdown.",
  "detalle": {{
    "error": "2-3 sentences: what specifically was wrong or missing and why it matters.",
    "micro_explicacion": "2-3 sentences: the core concept in plain words. What it is and why it happens. No jargon.",
    "respuesta_correcta": "The ideal answer a student should give: clear, complete, natural language. Both WHAT and WHY. 3-5 sentences.",
    "analogia": "{analogia_instruction}"
  }}
}}

RULES:
- "mensaje" is read aloud — spoken language only, no bullet points or markdown
- detalle fields appear as text cards — be rich and clear, but not overly long
- Never give away the correct answer in MEDIO responses
- Penalize Dunning-Kruger: confident but wrong → MAL, not MEDIO"""


def calcular_similitud(embedding_respuesta: list, embedding_atomo: list) -> float:
    v1 = np.array(embedding_respuesta)
    v2 = np.array(embedding_atomo)
    return float(max(0.0, min(1.0, np.dot(v1, v2))))


async def evaluar_respuesta(
    respuesta_usuario: str,
    atomo_texto: str,
    atomo_embedding: list,
    pregunta: str,
    uso_pista: bool = False,
    lang: str = "es",
    en_segundo_intento: bool = False,
    tema_analogia: str = "",
) -> Tuple[str, float, str, Optional[dict]]:
    """
    Evalúa la respuesta. Devuelve (ruta, similitud_coseno, feedback_voz, detalle).
    - ruta:    'verde' | 'amarillo' | 'rojo'
    - detalle: dict con {error, micro_explicacion, respuesta_correcta, analogia} solo para rojo; None si no
    Si uso_pista=True, la nota máxima es AMARILLO.
    """
    inicio = datetime.now()

    embedding_respuesta = embed_texto(respuesta_usuario)
    similitud = calcular_similitud(embedding_respuesta, atomo_embedding)

    lang_fb = _LANG_FEEDBACK.get(lang, _LANG_FEEDBACK["es"])
    detalle = None

    if similitud >= UMBRAL_FAST_VERDE:
        ruta = "verde"
        feedback = lang_fb["fast_verde"]
        logger.info(f"Evaluación: similitud={similitud:.3f} → verde (fast)")

    elif similitud >= UMBRAL_AUTO_VERDE:
        ruta = "verde"
        feedback = await _feedback_verde(pregunta, respuesta_usuario, atomo_texto, lang=lang)
        logger.info(f"Evaluación: similitud={similitud:.3f} → verde (auto)")

    else:
        ruta, feedback, detalle = await _evaluar_con_llm(
            pregunta=pregunta,
            respuesta_usuario=respuesta_usuario,
            respuesta_correcta=atomo_texto,
            lang=lang,
            en_segundo_intento=en_segundo_intento,
            tema_analogia=tema_analogia,
        )
        logger.info(f"Evaluación: similitud={similitud:.3f} → {ruta} (LLM)")

    # Penalización por pista: cap a AMARILLO
    if uso_pista and ruta == "verde":
        ruta = "amarillo"
        feedback = feedback + lang_fb["pista_penalty"]
        logger.info("Penalización pista: verde → amarillo")

    duracion = (datetime.now() - inicio).total_seconds()
    logger.info(f"Evaluación completada en {duracion:.2f}s (respuesta: '{respuesta_usuario[:60]}')")
    return ruta, similitud, feedback, detalle


async def _evaluar_con_llm(
    pregunta: str,
    respuesta_usuario: str,
    respuesta_correcta: str,
    lang: str = "es",
    en_segundo_intento: bool = False,
    tema_analogia: str = "",
) -> Tuple[str, str, Optional[dict]]:
    """LLM evalúa con metodología Feynman. Devuelve (ruta, feedback, detalle|None)."""
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])

    segundo_note = ""
    if en_segundo_intento:
        segundo_note = (
            "IMPORTANT — SECOND ATTEMPT: Be stricter. "
            "If they fail again → MAL. "
            "If improved but still incomplete → MEDIO. "
            "Only BIEN for clearly demonstrated understanding."
        )

    if tema_analogia:
        analogia_instr = (
            f"Write a vivid, memorable analogy that makes this concept genuinely click. "
            f"Build it as a short story or scenario — 4 to 5 sentences. "
            f"First, set the scene with a situation the student can picture. "
            f"Then develop the parallel step by step, showing how each part of the situation maps to the concept. "
            f"End with one sentence that connects it back explicitly to what they need to remember. "
            f"Prefer a scenario connected to: {tema_analogia}. If it doesn't fit naturally, use cooking, sport, money, or school instead. "
            f"Zero technical jargon. Write as if explaining to a curious 12-year-old."
        )
    else:
        analogia_instr = (
            "Write a vivid, memorable analogy that makes this concept genuinely click. "
            "Build it as a short story or scenario — 4 to 5 sentences. "
            "First, set the scene with a situation the student can picture. "
            "Then develop the parallel step by step, showing how each part of the situation maps to the concept. "
            "End with one sentence that connects it back explicitly to what they need to remember. "
            "Use cooking, sport, money, school, or nature scenarios. "
            "Zero technical jargon. Write as if explaining to a curious 12-year-old."
        )

    system_prompt = PROMPT_SISTEMA.format(
        lang_instruction=lang_instr,
        segundo_intento_note=segundo_note,
        analogia_instruction=analogia_instr,
    )

    lang_names = {"es": "Spanish", "en": "English", "de": "German"}
    lang_name = lang_names.get(lang, "Spanish")

    user_content = (
        f"[WRITE YOUR RESPONSE IN {lang_name.upper()} ONLY]\n\n"
        f"Question: {pregunta}\n"
        f"Concept: {respuesta_correcta[:600]}\n"
        f"Student answer: {respuesta_usuario}"
    )

    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
            max_tokens=700,
        )

    try:
        async with GROQ_LLM_SEM:
            response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=20.0)
        raw = response.choices[0].message.content.strip()
    except asyncio.TimeoutError:
        logger.warning("Evaluación LLM timeout — marcando como rojo con feedback genérico")
        _fb = {"es": "No pude evaluar a tiempo. Intenta de nuevo.", "en": "Evaluation timed out. Please try again.", "de": "Die Bewertung hat zu lange gedauert. Bitte versuche es erneut."}
        return "rojo", _fb.get(lang, _fb["en"]), None

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])

        clasificacion = data.get("clasificacion", "mal")
        ruta = {"bien": "verde", "medio": "amarillo", "mal": "rojo"}.get(clasificacion, "rojo")
        if ruta not in ("verde", "amarillo", "rojo"):
            ruta = "rojo"

        feedback = data.get("mensaje", "")
        detalle = data.get("detalle") if ruta == "rojo" else None
        # Ensure detalle is a dict if present
        if detalle is not None and not isinstance(detalle, dict):
            detalle = None

    except Exception:
        logger.warning(f"Evaluación: JSON parse failed — raw: {raw[:200]}")
        ruta = "rojo"
        feedback = raw[:300]
        detalle = None

    return ruta, feedback, detalle


async def _feedback_verde(
    pregunta: str,
    respuesta_usuario: str,
    respuesta_correcta: str,
    lang: str = "es",
) -> str:
    """Para similitud alta (auto-verde): genera elogio breve con LLM."""
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    lang_names = {"es": "Spanish", "en": "English", "de": "German"}
    lang_name = lang_names.get(lang, "Spanish")

    system_prompt = (
        f"{lang_instr}\n\n"
        f"You are a warm, encouraging tutor. The student answered correctly. "
        f"Give 2 natural spoken sentences praising them — mention specifically what they got right. "
        f"Sound genuine, not hollow. No bullet points or markdown. "
        f"Write exclusively in {lang_name}."
    )
    user_content = (
        f"[WRITE IN {lang_name.upper()} ONLY]\n\n"
        f"Question: {pregunta}\n"
        f"Correct concept: {respuesta_correcta[:300]}\n"
        f"Student answer: {respuesta_usuario}"
    )

    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.6,
            max_tokens=100,
        )

    try:
        async with GROQ_LLM_SEM:
            response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=10.0)
        return response.choices[0].message.content.strip()
    except Exception:
        lang_fb = _LANG_FEEDBACK.get(lang, _LANG_FEEDBACK["es"])
        return lang_fb["fast_verde"]
