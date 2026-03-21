"""
Evalúa la respuesta del usuario usando enfoque híbrido:
  - Si similitud coseno es muy alta (≥0.82) → verde directo
  - Si similitud coseno es muy baja  (<0.30) → rojo directo
  - Para el resto (zona gris): LLM hace el juicio definitivo

Un solo LLM call produce juicio + feedback juntos.
"""

import asyncio
import json
from datetime import datetime
from typing import Tuple

import numpy as np
from groq import Groq

from config import settings
from core.limits import GROQ_LLM_SEM
from core.vectorizer import embed_texto
from utils.logger import get_logger

logger = get_logger(__name__)

groq_client = Groq(api_key=settings.groq_api_key)

# Umbrales para saltar el LLM (casos claros)
UMBRAL_AUTO_VERDE = 0.82   # Similitud muy alta → verde sin LLM
UMBRAL_AUTO_ROJO  = 0.30   # Similitud muy baja  → rojo sin LLM

# Umbrales para saltar incluso el feedback LLM (casos inequívocos — respuesta instantánea)
UMBRAL_FAST_VERDE = 0.92   # Muy alta similitud → feedback plantilla, 0 LLM calls
UMBRAL_FAST_ROJO  = 0.12   # Claramente sin relación → feedback plantilla, 0 LLM calls


PROMPT_SISTEMA = """Eres un tutor académico que evalúa respuestas de estudiantes.

TAREA: Evalúa si el estudiante respondió correctamente y genera feedback breve.

CRITERIOS (sé ESTRICTO):
- verde: la respuesta contiene el concepto clave de forma correcta y completa
- amarillo: tiene algo correcto pero falta información importante o esencial
- rojo: la respuesta es incorrecta, es solo la pregunta reformulada, es vaga, irrelevante, o no responde lo pedido

IMPORTANTE:
- Si el estudiante solo repite la pregunta o hace preguntas en vez de responder → ROJO
- Si menciona términos del tema pero no responde la pregunta concreta → ROJO
- Si la respuesta es incompleta pero capta la idea central → AMARILLO

FORMATO DE RESPUESTA — solo JSON, sin nada más:
{"ruta": "verde|amarillo|rojo", "feedback": "2-3 frases naturales de tutor oral"}

El feedback debe ser conversacional (se leerá en voz alta), no uses listas ni bullet points."""


def calcular_similitud(embedding_respuesta: list, embedding_atomo: list) -> float:
    v1 = np.array(embedding_respuesta)
    v2 = np.array(embedding_atomo)
    return float(max(0.0, min(1.0, np.dot(v1, v2))))


_LANG_FEEDBACK = {
    "es": {
        "fast_verde": "¡Perfecto! Lo tienes muy claro. Pasamos a la siguiente.",
        "fast_rojo": "Eso no es correcto. Repasa el concepto que te explico a continuación.",
        "pista_penalty": " (Has usado una pista, así que lo anotamos como amarillo.)",
        "lang_instruction": "Responde SIEMPRE en español.",
    },
    "en": {
        "fast_verde": "Perfect! You've got it down. Moving on to the next one.",
        "fast_rojo": "That's not correct. Review the concept I'll explain next.",
        "pista_penalty": " (You used a hint, so we'll mark this as partial.)",
        "lang_instruction": "ALWAYS respond in English.",
    },
    "de": {
        "fast_verde": "Perfekt! Das hast du sehr gut verstanden. Weiter zur nächsten Frage.",
        "fast_rojo": "Das ist nicht korrekt. Schau dir das Konzept an, das ich dir gleich erkläre.",
        "pista_penalty": " (Du hast einen Hinweis benutzt, daher markieren wir dies als teilweise richtig.)",
        "lang_instruction": "Antworte IMMER auf Deutsch.",
    },
}

async def evaluar_respuesta(
    respuesta_usuario: str,
    atomo_texto: str,
    atomo_embedding: list,
    pregunta: str,
    uso_pista: bool = False,
    lang: str = "es",
) -> Tuple[str, float, str]:
    """
    Evalúa la respuesta. Devuelve (ruta, similitud_coseno, feedback_voz).
    Si uso_pista=True, la nota máxima es AMARILLO (penalización por pista).
    """
    inicio = datetime.now()

    # 1. Similitud coseno
    embedding_respuesta = embed_texto(respuesta_usuario)
    similitud = calcular_similitud(embedding_respuesta, atomo_embedding)

    lang_fb = _LANG_FEEDBACK.get(lang, _LANG_FEEDBACK["es"])

    # 2. Casos claros: saltar LLM
    if similitud >= UMBRAL_FAST_VERDE:
        # Caso inequívoco verde: feedback plantilla instantáneo, sin LLM
        ruta = "verde"
        feedback = lang_fb["fast_verde"]
        logger.info(f"Evaluación: similitud={similitud:.3f} → verde (fast)")
    elif similitud < UMBRAL_FAST_ROJO:
        # Caso inequívoco rojo: feedback plantilla instantáneo, sin LLM
        ruta = "rojo"
        feedback = lang_fb["fast_rojo"]
        logger.info(f"Evaluación: similitud={similitud:.3f} → rojo (fast)")
    elif similitud >= UMBRAL_AUTO_VERDE:
        ruta = "verde"
        feedback = await _feedback_rapido("verde", pregunta, respuesta_usuario, atomo_texto, lang=lang)
        logger.info(f"Evaluación: similitud={similitud:.3f} → verde (auto)")
    elif similitud < UMBRAL_AUTO_ROJO:
        ruta = "rojo"
        feedback = await _feedback_rapido("rojo", pregunta, respuesta_usuario, atomo_texto, lang=lang)
        logger.info(f"Evaluación: similitud={similitud:.3f} → rojo (auto)")
    else:
        # 3. Zona gris: LLM decide ruta + genera feedback
        ruta, feedback = await _evaluar_con_llm(pregunta, respuesta_usuario, atomo_texto, lang=lang)
        logger.info(f"Evaluación: similitud={similitud:.3f} → {ruta} (LLM)")

    # Penalización por pista: cap a AMARILLO
    if uso_pista and ruta == "verde":
        ruta = "amarillo"
        feedback = feedback + lang_fb["pista_penalty"]
        logger.info(f"Penalización pista: verde → amarillo")

    duracion = (datetime.now() - inicio).total_seconds()
    logger.info(f"Evaluación completada en {duracion:.2f}s (respuesta: '{respuesta_usuario[:60]}')")
    return ruta, similitud, feedback


async def _evaluar_con_llm(
    pregunta: str,
    respuesta_usuario: str,
    respuesta_correcta: str,
    lang: str = "es",
) -> Tuple[str, str]:
    """LLM evalúa y genera feedback. Devuelve (ruta, feedback)."""
    lang_instr = _LANG_FEEDBACK.get(lang, _LANG_FEEDBACK["es"])["lang_instruction"]
    system_prompt = PROMPT_SISTEMA + f"\n\n{lang_instr}"
    user_content = (
        f"Pregunta: {pregunta}\n"
        f"Respuesta esperada: {respuesta_correcta}\n"
        f"Respuesta del estudiante: {respuesta_usuario}"
    )
    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=200,
        )

    async with GROQ_LLM_SEM:
        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=10.0)
    raw = response.choices[0].message.content.strip()

    # Parsear JSON
    try:
        # Extraer JSON aunque haya texto extra
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        ruta = data.get("ruta", "rojo")
        if ruta not in ("verde", "amarillo", "rojo"):
            ruta = "rojo"
        feedback = data.get("feedback", "")
    except Exception:
        # Fallback si el JSON falla
        ruta = "rojo"
        feedback = raw[:300]

    return ruta, feedback


async def _feedback_rapido(
    ruta: str,
    pregunta: str,
    respuesta_usuario: str,
    respuesta_correcta: str,
    lang: str = "es",
) -> str:
    """Para casos auto (muy claro), genera solo el feedback con el LLM."""
    lang_instr = _LANG_FEEDBACK.get(lang, _LANG_FEEDBACK["es"])["lang_instruction"]
    prompts_sistema = {
        "verde": f"You are an enthusiastic tutor. The student answered correctly. Give 1-2 sentences praising them. Be natural and brief. {lang_instr}",
        "rojo": f"You are an empathetic tutor. The student couldn't answer. In 2 sentences explain the correct answer clearly. No lists. {lang_instr}",
    }
    user_content = (
        f"Pregunta: {pregunta}\n"
        f"Respuesta del estudiante: {respuesta_usuario}\n"
        f"Respuesta correcta: {respuesta_correcta}"
    )
    def _call():
        return groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": prompts_sistema[ruta]},
                {"role": "user", "content": user_content},
            ],
            temperature=0.6,
            max_tokens=120,
        )

    async with GROQ_LLM_SEM:
        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=10.0)
    return response.choices[0].message.content.strip()
