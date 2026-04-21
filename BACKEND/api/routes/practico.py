"""
practico.py — REST endpoints for the Practical Learning Module

Routes:
  GET  /practico/ejercicios          — list exercises (filterable)
  GET  /practico/ejercicio/{id}      — single exercise with full blocks
  GET  /practico/formulas            — list formulas
  POST /practico/generar             — AI-generate exercises from topic atoms (no DB write)
  POST /practico/sesion/start        — start a practice session (returns shuffled exercises)
  POST /practico/sesion/resultado    — record per-exercise correctness
"""

import json
import random
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)
router = APIRouter(prefix="/practico", tags=["practico"])


# ──────────────────────────────────────────────
# GET /practico/ejercicios
# ──────────────────────────────────────────────
@router.get("/ejercicios")
async def listar_ejercicios(
    asignatura_id:  str = Query(...),
    documento_id:   str | None = Query(None),
    tipo:           str | None = Query(None),
    tipo_contenido: str | None = Query(None),   # ejercicio | procedimiento | concepto
    dificultad:     int | None = Query(None),
    limit:          int = Query(100, ge=1, le=500),
):
    db = get_service_client()
    q = (
        db.table("ejercicios")
        .select("id, tema, tipo, tipo_contenido, titulo, dificultad, enunciado, solucion, dades, created_at")
        .eq("asignatura_id", asignatura_id)
        .order("tipo_contenido")   # concepto → ejercicio → procedimiento (alphabetical groups)
        .order("created_at")
        .limit(limit)
    )
    if documento_id:
        q = q.eq("documento_id", documento_id)
    if tipo:
        q = q.eq("tipo", tipo)
    if tipo_contenido:
        q = q.eq("tipo_contenido", tipo_contenido)
    if dificultad is not None:
        q = q.eq("dificultad", dificultad)

    res = q.execute()
    return res.data or []


# ──────────────────────────────────────────────
# GET /practico/ejercicio/{id}
# ──────────────────────────────────────────────
@router.get("/ejercicio/{ejercicio_id}")
async def get_ejercicio(ejercicio_id: str):
    db = get_service_client()
    res = (
        db.table("ejercicios")
        .select("*")
        .eq("id", ejercicio_id)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    return res.data


# ──────────────────────────────────────────────
# GET /practico/formulas
# ──────────────────────────────────────────────
@router.get("/formulas")
async def listar_formulas(
    asignatura_id: str = Query(...),
    documento_id:  str | None = Query(None),
    tema:          str | None = Query(None),
):
    db = get_service_client()
    q = (
        db.table("formulas_tema")
        .select("*")
        .eq("asignatura_id", asignatura_id)
        .order("created_at")
    )
    if documento_id:
        q = q.eq("documento_id", documento_id)
    if tema:
        q = q.eq("tema", tema)

    res = q.execute()
    return res.data or []


# ──────────────────────────────────────────────
# POST /practico/generar
# ──────────────────────────────────────────────

PROMPT_GENERAR = """
Eres un profesor experto. Basándote ÚNICAMENTE en el siguiente contenido de los apuntes,
crea exactamente {n} ejercicios originales y resueltos.

CONOCIMIENTO DISPONIBLE:
{contexto}

FÓRMULAS DE REFERENCIA:
{formulas}

Devuelve SOLO el siguiente JSON sin texto adicional, sin markdown, sin ```json:

{{
  "ejercicios": [
    {{
      "titulo": "string — título corto descriptivo del ejercicio",
      "enunciado": [
        {{ "type": "text", "content": "enunciado del ejercicio con datos concretos" }},
        {{ "type": "math", "latex": "expresión LaTeX SIN delimitadores $ ni $$" }}
      ],
      "solucion": [
        {{
          "type": "step",
          "n": 1,
          "content": [
            {{ "type": "text", "content": "explicación del paso" }},
            {{ "type": "math", "latex": "expresión LaTeX SIN delimitadores $ ni $$" }}
          ]
        }}
      ]
    }}
  ]
}}

REGLAS:
- Crea exactamente {n} ejercicios DISTINTOS y originales basados en el contenido dado.
- Cada ejercicio debe tener datos numéricos concretos y ser resoluble.
- La solución debe tener entre 2 y 5 pasos claros y numerados.
- LaTeX: escribe SOLO el contenido matemático, SIN $ ni $$.
- Idioma de los textos: {lang}.
- NO inventes conceptos fuera del contenido dado.
""".strip()


class GenerarBody(BaseModel):
    asignatura_id: str
    temas_ids: list[str]
    n: int = 3
    lang: str = "es"


@router.post("/generar")
async def generar_ejercicios(body: GenerarBody):
    """
    AI-generates N original exercises from the atoms of the selected subtemas.
    No DB persistence — pure on-demand generation.
    """
    from core.practical_extractor import _client
    from config import settings
    from google.genai import types as gtypes

    db = get_service_client()
    n = max(1, min(10, body.n))

    # 1. Fetch atoms for the given subtema IDs
    atomos_rows: list[dict] = []
    if body.temas_ids:
        res = (
            db.table("atomos")
            .select("pregunta, respuesta, subtema_id")
            .in_("subtema_id", body.temas_ids)
            .limit(80)
            .execute()
        )
        atomos_rows = res.data or []

    if not atomos_rows:
        return {"ejercicios": [], "error": "No hay contenido para los temas seleccionados"}

    contexto = "\n\n".join(
        f"P: {a['pregunta']}\nR: {a['respuesta']}"
        for a in atomos_rows
        if a.get("pregunta") and a.get("respuesta")
    )

    # 2. Fetch formulas for context
    fres = (
        db.table("formulas_tema")
        .select("nombre, latex")
        .eq("asignatura_id", body.asignatura_id)
        .limit(20)
        .execute()
    )
    formulas_ctx = "\n".join(
        f"- {f['nombre']}: {f['latex']}"
        for f in (fres.data or [])
        if f.get("latex")
    ) or "Ninguna disponible"

    # 3. Build prompt and call Gemini
    prompt = PROMPT_GENERAR.format(
        n=n,
        contexto=contexto[:8000],
        formulas=formulas_ctx[:2000],
        lang=body.lang,
    )

    try:
        response = _client.models.generate_content(
            model=settings.gemini_model,
            contents=[prompt],
            config=gtypes.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}
        ejercicios = parsed.get("ejercicios", []) or []
        logger.info(f"[generar] Generated {len(ejercicios)} exercises for asignatura {body.asignatura_id}")
    except Exception as e:
        logger.warning(f"[generar] Gemini error: {e}")
        return {"ejercicios": [], "error": str(e)}

    return {"ejercicios": ejercicios}


# ──────────────────────────────────────────────
# POST /practico/sesion/start
# ──────────────────────────────────────────────
class SesionStartBody(BaseModel):
    asignatura_id: str
    documento_id:  str | None = None
    tipo:          str | None = None
    n:             int = 5    # number of exercises to return


@router.post("/sesion/start")
async def start_sesion(body: SesionStartBody):
    """
    Returns a shuffled list of exercises for a practice session.
    Also returns associated formulas so the frontend can show them in DADES.
    """
    db = get_service_client()

    # Fetch only exercises (not procedures/concepts) for practice sessions
    q = (
        db.table("ejercicios")
        .select("*")
        .eq("asignatura_id", body.asignatura_id)
        .eq("tipo_contenido", "ejercicio")
    )
    if body.documento_id:
        q = q.eq("documento_id", body.documento_id)
    if body.tipo:
        q = q.eq("tipo", body.tipo)

    res = q.execute()
    ejercicios = res.data or []

    if not ejercicios:
        return {"ejercicios": [], "formulas": []}

    # Shuffle and cap at n
    random.shuffle(ejercicios)
    ejercicios = ejercicios[: body.n]

    # Fetch formulas for context
    fq = db.table("formulas_tema").select("*").eq("asignatura_id", body.asignatura_id)
    if body.documento_id:
        fq = fq.eq("documento_id", body.documento_id)
    fres = fq.execute()
    formulas = fres.data or []

    return {
        "ejercicios": ejercicios,
        "formulas": formulas,
    }


# ──────────────────────────────────────────────
# POST /practico/sesion/resultado
# ──────────────────────────────────────────────
class ResultadoBody(BaseModel):
    usuario_id:   str
    ejercicio_id: str
    correcto:     bool


@router.post("/sesion/resultado")
async def registrar_resultado(body: ResultadoBody):
    db = get_service_client()
    res = (
        db.table("practica_resultados")
        .insert({
            "usuario_id":   body.usuario_id,
            "ejercicio_id": body.ejercicio_id,
            "correcto":     body.correcto,
        })
        .execute()
    )
    return {"ok": True, "id": res.data[0]["id"] if res.data else None}


# ──────────────────────────────────────────────
# GET /practico/stats/{usuario_id}
# ──────────────────────────────────────────────
@router.get("/stats/{usuario_id}")
async def get_stats(usuario_id: str, asignatura_id: str = Query(...)):
    """Returns total / correct / incorrect counts for dashboard."""
    db = get_service_client()
    res = (
        db.table("practica_resultados")
        .select("correcto, ejercicio_id, ejercicios!inner(asignatura_id)")
        .eq("usuario_id", usuario_id)
        .eq("ejercicios.asignatura_id", asignatura_id)
        .execute()
    )
    rows = res.data or []
    total   = len(rows)
    correct = sum(1 for r in rows if r.get("correcto"))
    return {
        "total":     total,
        "correcto":  correct,
        "incorrecto": total - correct,
    }
