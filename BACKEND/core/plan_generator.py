"""
Generador de planes de estudio — v2.
Sistema dinámico de dos capas:
  Capa 1: sesiones INITIAL (exposición progresiva)
  Capa 2: sesiones REVIEW generadas automáticamente (spaced repetition real)

Soporta modo intensivo intradía (1-2 días) y modos acelerado/completo.
"""

import asyncio
import json
import traceback
from datetime import date

from groq import Groq

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_groq = Groq(api_key=settings.groq_api_key)

_LANG_INSTRUCTION = {
    "es": "IDIOMA OBLIGATORIO: español. Escribe TODO el JSON ÚNICAMENTE EN ESPAÑOL.",
    "en": "MANDATORY LANGUAGE: English. Write ALL JSON content EXCLUSIVELY IN ENGLISH.",
    "de": "PFLICHTSPRACHE: Deutsch. Schreibe ALLE JSON-Inhalte AUSSCHLIESSLICH AUF DEUTSCH.",
}

PROMPT_PLAN = """{lang_instruction}

Eres un sistema avanzado de generación de planes de estudio para una app basada en Active Recall y Spaced Repetition.

CONTEXTO DE LA APP:
- El usuario estudia dentro de una asignatura con temas y átomos (unidades de conocimiento).
- Un plan organiza sesiones de preguntas/respuestas (Active Recall).
- El usuario define cuántas preguntas quiere por sesión (questions_per_session).

INPUTS:
- exam_date: {exam_date}
- today: {today}
- selected_atoms: {selected_atoms}
- diagnostic_results: {diagnostic_results}
- intensity: {intensity}
- questions_per_session: {questions_per_session}

---

FLUJO OBLIGATORIO DEL SISTEMA — SIGUE ESTE ORDEN SIEMPRE:

PASO 1 — DIAGNÓSTICO
Si diagnostic_results está vacío o incompleto:
  - Marca needs_diagnostic = true en la respuesta.
  - Crea UNA sesión de tipo "diagnostic" en today con TODOS los átomos seleccionados.
  - Esta sesión evalúa el nivel del usuario ANTES de planificar.
  - Sin diagnóstico el plan no puede optimizarse.

Si diagnostic_results tiene datos para todos los átomos:
  - Usa esos datos directamente. needs_diagnostic = false.
  - Clasifica cada átomo:
      bajo  = estado "rojo"  (fallo)
      medio = estado "amarillo" (parcial)
      alto  = estado "verde"  (dominio)

PASO 2 — CALCULAR MODO SEGÚN DÍAS HASTA EXAMEN
  dias = días naturales entre hoy y exam_date
  1–2 días  → strategy_mode = "intensive"   (spaced repetition intradía por horas)
  3–7 días  → strategy_mode = "accelerated"
  8+ días   → strategy_mode = "full"

PASO 3 — CAPA 1: SESIONES INITIAL
  - Distribuir los átomos a lo largo de los días disponibles.
  - Prioridad de exposición: bajo → medio → alto.
  - NO llenar todos los días con sesiones initial. Dejar hueco para review.
  - Exposición progresiva: máximo 60% de los átomos en los primeros 50% de los días.
  - Carga diaria dinámica: no fija. Calcular según dias_restantes + intensity + n_atomos.

PASO 4 — CAPA 2: SPACED REPETITION AUTOMÁTICO
  Por cada sesión initial, generar automáticamente sesiones review.

  MODO NORMAL (3+ días):
    bajo  (rojo)    → review en 1 día
    medio (amarillo)→ review en 2-3 días
    alto  (verde)   → review en 4-7 días

  MODO INTENSIVO (1-2 días) — spaced repetition intradía:
    Día 1 mañana (slot=morning)   → initial
    Día 1 tarde  (slot=afternoon) → review de lo de la mañana
    Día 1 noche  (slot=evening)   → review reforzado (si hubo errores)
    Día 2        (slot=morning)   → repaso global + reinforcement de errores

REGLAS ADICIONALES:
- Las sesiones review tienen is_review_session = true y MÁXIMA PRIORIDAD.
- Si hay una review pendiente, BLOQUEA el avance (blocking_enabled = true).
- Si el usuario usa skip en review: la sesión se mueve al día siguiente (NO se duplica).
- Cada átomo debe aparecer AL MENOS 2 veces antes del examen (initial + review).
- Los átomos "bajo" deben aparecer al menos 3 veces.

INTENSITY define agresividad:
  rapido     → más sesiones/día, menos separación entre reviews
  equilibrado → balance entre carga y retención
  exhaustivo  → más repeticiones, más espacio, mayor profundidad

ERRORES A EVITAR:
  ❌ Planes sin sesiones review reales
  ❌ Todos los repasos al final del plan
  ❌ Carga fija por día (siempre el mismo número de sesiones)
  ❌ Tratar review como opcional
  ❌ No adaptar al modo intensivo (1-2 días)
  ❌ No usar diagnóstico cuando es necesario

---

Retorna ÚNICAMENTE JSON válido con esta estructura exacta (sin markdown, sin texto extra):

{{
  "needs_diagnostic": false,
  "strategy_mode": "full | accelerated | intensive",
  "today": [
    {{
      "session_id": 1,
      "type": "diagnostic | initial | review | reinforcement",
      "slot": "morning | afternoon | evening | anytime",
      "atoms": ["atom_id_1", "atom_id_2"],
      "number_of_questions": 10,
      "estimated_duration_min": 10,
      "is_review_session": false,
      "day_offset": 0
    }}
  ],
  "next_days": [
    {{
      "day": 1,
      "sessions": [
        {{
          "type": "initial | review | reinforcement",
          "slot": "morning | afternoon | evening | anytime",
          "atoms": ["atom_id_3"],
          "number_of_questions": 8,
          "estimated_duration_min": 8,
          "is_review_session": true,
          "day_offset": 1
        }}
      ]
    }}
  ],
  "review_rules": {{
    "blocking_enabled": true,
    "review_priority": "highest",
    "skip_moves_to_next_day": true
  }}
}}""".strip()


def _parse_plan(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    data = json.loads(text)
    return data


async def generar_plan_de_estudio(
    exam_date: str,
    selected_atoms: list[dict],
    diagnostic_results: dict,
    intensity: str = "equilibrado",
    lang: str = "es",
    questions_per_session: int = 10,
) -> dict:
    """
    Genera un plan de estudio adaptativo de dos capas:
      Capa 1: sesiones INITIAL distribuidas progresivamente
      Capa 2: sesiones REVIEW con spaced repetition real

    Si no hay diagnóstico previo, devuelve needs_diagnostic=True y una sesión diagnóstica.
    """
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    today_str = date.today().isoformat()

    atoms_str = json.dumps(selected_atoms, ensure_ascii=False)
    diag_str = json.dumps(diagnostic_results, ensure_ascii=False)

    prompt = PROMPT_PLAN.format(
        exam_date=exam_date,
        today=today_str,
        selected_atoms=atoms_str,
        diagnostic_results=diag_str,
        intensity=intensity,
        questions_per_session=questions_per_session,
        lang_instruction=lang_instr,
    )

    # ── Groq (primary — fast) ────────────────────────────────────────────────
    def _groq_call():
        return _groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=6000,
            response_format={"type": "json_object"},
        )

    try:
        response = await asyncio.wait_for(asyncio.to_thread(_groq_call), timeout=40.0)
        plan = _parse_plan(response.choices[0].message.content)
        if plan:
            logger.info(f"Plan v2 generado con Groq [{lang}] — mode={plan.get('strategy_mode')} needs_diagnostic={plan.get('needs_diagnostic')}")
            return plan
        logger.warning("Groq devolvió data inválida — intentando Gemini")
    except asyncio.TimeoutError:
        logger.warning("Groq timeout (40s) generando plan — intentando Gemini")
    except Exception:
        logger.warning(f"Groq falló generando plan:\n{traceback.format_exc()}")

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
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )

        async with GEMINI_SEM:
            response = await asyncio.wait_for(asyncio.to_thread(_gemini_call), timeout=50.0)

        plan = _parse_plan(response.text)
        if plan:
            logger.info(f"Plan v2 generado con Gemini fallback [{lang}]")
            return plan
    except asyncio.TimeoutError:
        logger.error("Gemini timeout (50s) generando plan — fallback fallido")
    except Exception:
        logger.error(f"Gemini falló generando plan:\n{traceback.format_exc()}")

    return {}
