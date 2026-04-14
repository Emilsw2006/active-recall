"""
Generador de planes de estudio con Groq + Gemini como fallback.
Utiliza llm para distribuir sesiones, espaciar repaso y manejar bloqueos por repaso.
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

Eres un sistema de generación de planes de estudio para una app de aprendizaje con Active Recall y Spaced Repetition.

CONTEXTO DE LA APP:
- El usuario estudia dentro de una asignatura.
- La asignatura contiene temas y átomos (subtemas).
- El usuario crea un PLAN dentro de la asignatura.
- El plan organiza sesiones de estudio tipo preguntas/respuestas.

INPUTS:
- exam_date: {exam_date}
- selected_atoms: {selected_atoms}
- diagnostic_results: {diagnostic_results}
- intensity: {intensity}

OBJETIVO:
Crear un plan de sesiones de estudio optimizado para llegar al examen dominando los átomos seleccionados.

REGLAS DE ESTRATEGIA:

1. Calcular días restantes hasta el examen.

2. Definir modo del plan automáticamente:
- 1–2 días → modo intensivo
- 3–7 días → modo acelerado
- >7 días → modo completo

3. Generación de sesiones:
Una sesión es una unidad de estudio basada en preguntas de átomos.

Cada sesión debe incluir:
- type: initial / reinforcement / review
- atoms (subconjunto de los seleccionados)
- number_of_questions (calculado automáticamente según tiempo y dificultad)
- estimated_duration_min (5–15 min)

4. Priorización:
- primero átomos con peor diagnóstico
- luego átomos medios
- asegurar cobertura mínima de todos los átomos seleccionados

5. Repetición (spaced repetition):
- error alto → repetir en 1 día
- error medio → repetir en 2–3 días
- error bajo → repetir en 4–7 días

6. Lógica de aprendizaje:
- initial = primera exposición a un átomo
- reinforcement = refuerzo de errores
- review = repaso espaciado

---

NUEVA REGLA: SISTEMA DE REPASO Y BLOQUEO (INTEGRADO EN EL PLAN)

Durante la generación del plan, el sistema debe detectar sesiones de tipo REVIEW y gestionarlas así:

A) MARCADO DE SESIONES DE REPASO:
- cualquier sesión generada por errores acumulados o repetición se marca como:
  "is_review_session": true

B) PRIORIDAD VISUAL:
- las sesiones con "is_review_session": true deben aparecer:
  - primero en TODAY si caen en el día actual
  - con prioridad visual alta en la UI (destacadas)

C) REGLA DE BLOQUEO (CONCEPTUAL PARA LA APP):
- si existe una sesión de repaso activa en TODAY:
  - debe bloquear la creación o ejecución de nuevas sesiones normales dentro del plan hasta completarla
  - SOLO se permite:
    - completar la sesión de repaso
    - o usar skip (si el sistema lo permite)

D) SKIP HANDLING:
- si el usuario usa skip en una sesión de repaso:
  - la sesión permanece activa
  - se mantiene como primera acción obligatoria del día siguiente
  - no se genera nueva sesión de repaso adicional ese día

E) RESET DEL SISTEMA:
- cuando una sesión de repaso se completa:
  - se eliminan flags de bloqueo
  - se continúa el plan normal

Retorna ÚNICAMENTE JSON válido con esta estructura, sin markdown (excepto si usas formato JSON), sin texto extra:

{{
  "strategy_mode": "intensive | accelerated | full",
  "today": [
    {{
      "session_id": 1,
      "type": "initial | reinforcement | review",
      "atoms": ["id_atomo_1", "id_atomo_2"],
      "number_of_questions": 10,
      "estimated_duration_min": 10,
      "is_review_session": true
    }}
  ],
  "next_days": [
    {{
      "day": 1,
      "sessions": [
        {{
          "type": "initial | reinforcement | review",
          "atoms": ["id_atomo_3"],
          "number_of_questions": 5,
          "estimated_duration_min": 5,
          "is_review_session": false
        }}
      ]
    }}
  ],
  "review_rules": {{
    "blocking_enabled": true,
    "review_priority": "highest",
    "skip_allowed": true
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
    lang: str = "es"
) -> dict:
    """
    Genera un plan de estudio adaptativo usando LLM basado en los átomos, 
    diagnóstico y reglas de Spaced Repetition y bloqueo.
    """
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])
    
    atoms_str = json.dumps(selected_atoms, ensure_ascii=False)
    diag_str = json.dumps(diagnostic_results, ensure_ascii=False)
    
    prompt = PROMPT_PLAN.format(
        exam_date=exam_date,
        selected_atoms=atoms_str,
        diagnostic_results=diag_str,
        intensity=intensity,
        lang_instruction=lang_instr
    )

    # ── Groq (primary — fast) ────────────────────────────────────────────────
    def _groq_call():
        return _groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, # lower temperature for analytical generation
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

    try:
        response = await asyncio.wait_for(asyncio.to_thread(_groq_call), timeout=30.0)
        plan = _parse_plan(response.choices[0].message.content)
        if plan:
            logger.info(f"Plan generado con Groq [{lang}]")
            return plan
        logger.warning("Groq devolvió data inválida — intentando Gemini")
    except asyncio.TimeoutError:
        logger.warning("Groq timeout (30s) generando plan — intentando Gemini")
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
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )

        async with GEMINI_SEM:
            response = await asyncio.wait_for(asyncio.to_thread(_gemini_call), timeout=45.0)

        plan = _parse_plan(response.text)
        if plan:
            logger.info(f"Plan generado con Gemini fallback [{lang}]")
            return plan
    except asyncio.TimeoutError:
        logger.error("Gemini timeout (45s) generando plan — fallback fallido")
    except Exception:
        logger.error(f"Gemini falló generando plan:\n{traceback.format_exc()}")

    return {}
