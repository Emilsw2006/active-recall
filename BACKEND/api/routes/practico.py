"""
practico.py — REST endpoints for the Practical Learning Module

Routes:
  GET  /practico/ejercicios          — list exercises (filterable)
  GET  /practico/ejercicio/{id}      — single exercise with full blocks
  GET  /practico/formulas            — list formulas
  POST /practico/sesion/start        — start a practice session (returns shuffled exercises)
  POST /practico/sesion/resultado    — record per-exercise correctness
"""

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
        .select("id, tema, tipo, tipo_contenido, titulo, dificultad, enunciado, dades, created_at")
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
