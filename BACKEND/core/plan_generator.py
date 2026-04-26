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
- REGLA CRÍTICA: "number_of_questions" en CADA sesión debe ser EXACTAMENTE {questions_per_session}. Nunca uses otro valor.

INPUTS:
- exam_date: {exam_date}
- today: {today}
- total_atoms: {total_atoms}
- total_teoricos: {total_teoricos}
- total_practicos: {total_practicos}
- subtemas_breakdown (lista de subtemas con conteo por tipo): {subtemas_breakdown}
- diagnostic_results: {diagnostic_results}
- intensity: {intensity}
- questions_per_session: {questions_per_session}
- dias_hasta_examen: {dias}

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

PASO 3 — CAPA 1: SESIONES INITIAL (separadas por modo: oral vs practico)
  - n_sesiones_orales    = ceil(total_teoricos  / questions_per_session)
  - n_sesiones_practicas = ceil(total_practicos / questions_per_session)
  - n_sesiones_initial   = n_sesiones_orales + n_sesiones_practicas
  - Cada sesión TIENE UN ÚNICO MODO: "oral" (átomos teóricos por voz) o "practico" (ejercicios autoevaluados paso a paso).
  - Si un subtema es MIXTO (tiene teóricos y prácticos), genera SESIONES SEPARADAS: una oral con sus teóricos y una práctica con sus prácticos. Nunca mezcles modos en la misma sesión.
  - Distribuir las sesiones a lo largo de los dias disponibles, intercalando oral y práctico para variar.
  - Prioridad de exposición: bajo → medio → alto.
  - Reservar 1/3 de los días para sesiones review — NO llenar todos los días con initial.
  - Carga diaria dinámica según intensity:
      rapido: 2 sesiones/día max
      equilibrado: 1 sesión/día estudio + hueco para review
      exhaustivo: 1 sesión/día con muchas reviews

TÍTULO Y MODO POR SESIÓN — OBLIGATORIO:
  - Cada sesión DEBE incluir "modo" ("oral" | "practico") y "titulo" (máx 40 caracteres, descriptivo).
  - El título debe reflejar el subtema o concepto que esa sesión cubrirá. Ej: "Restricción presupuestaria", "Ejercicios: maximización", "Funciones de utilidad", "Repaso: elasticidad".
  - Para sesiones review, el título puede ser tipo "Repaso: <concepto>".
  - NO uses títulos genéricos como "Sesión 1" o "Estudio".

PASO 4 — CAPA 2: SPACED REPETITION
  - Por cada grupo de sesiones initial, crear review automático.
  - MODO NORMAL (3+ días):
      errores altos (rojo)    → review al día siguiente (day_offset + 1)
      errores medios (amarillo) → review a los 2-3 días
      errores bajos (verde)   → review a los 4-7 días
  - MODO INTENSIVO (1-2 días):
      Mañana → initial, Tarde → review, Noche → reinforcement si fallos
  - number_of_questions de TODAS las sesiones = {questions_per_session} (OBLIGATORIO)
  - is_review_session = true para review y reinforcement
  - day_offset = días desde hoy (0 = hoy, 1 = mañana, etc.)

REGLAS:
- TODAS las sesiones tienen "number_of_questions": {questions_per_session}
- Generar SUFICIENTES sesiones: al menos n_sesiones_initial initial + mismo número de reviews
- Los átomos "bajo/rojo" aparecen mínimo 3 veces, "medio" 2 veces, "alto" 1 vez
- blocking_enabled = true (review bloquea avance)

---

Retorna ÚNICAMENTE JSON válido (sin markdown, sin texto extra):

{{
  "needs_diagnostic": false,
  "strategy_mode": "full | accelerated | intensive",
  "today": [
    {{
      "type": "diagnostic | initial | review | reinforcement",
      "modo": "oral | practico",
      "titulo": "string (máx 40 chars, descriptivo del concepto)",
      "slot": "morning | afternoon | evening | anytime",
      "number_of_questions": {questions_per_session},
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
          "modo": "oral | practico",
          "titulo": "string (máx 40 chars, descriptivo del concepto)",
          "slot": "anytime",
          "number_of_questions": {questions_per_session},
          "is_review_session": false,
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

    # Agregación por (tema, subtema) con conteo por tipo (teorico/practico)
    breakdown_map: dict[tuple[str, str], dict[str, int]] = {}
    total_teoricos = 0
    total_practicos = 0
    for a in selected_atoms:
        key = (a.get("tema_titulo", ""), a.get("subtema_titulo", ""))
        rec = breakdown_map.setdefault(key, {"tema": key[0], "subtema": key[1], "n_teoricos": 0, "n_practicos": 0})
        if (a.get("tipo") or "teorico") == "practico":
            rec["n_practicos"] += 1
            total_practicos += 1
        else:
            rec["n_teoricos"] += 1
            total_teoricos += 1
    subtemas_breakdown = list(breakdown_map.values())
    breakdown_str = json.dumps(subtemas_breakdown, ensure_ascii=False)
    diag_str = json.dumps(diagnostic_results, ensure_ascii=False)

    from datetime import date as _date
    try:
        exam_dt = _date.fromisoformat(exam_date)
        dias = (exam_dt - _date.fromisoformat(today_str)).days
    except Exception:
        dias = 30

    prompt = PROMPT_PLAN.format(
        exam_date=exam_date,
        today=today_str,
        total_atoms=len(selected_atoms),
        total_teoricos=total_teoricos,
        total_practicos=total_practicos,
        subtemas_breakdown=breakdown_str,
        diagnostic_results=diag_str,
        intensity=intensity,
        questions_per_session=questions_per_session,
        dias=dias,
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
