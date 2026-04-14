"""
Endpoints de planes de estudio:
- POST /plan/crear                    → crea plan y genera sesiones distribuidas
- GET  /planes/usuario/{usuario_id}   → lista planes del usuario (filtrado por asignatura)
- GET  /plan/{plan_id}/proxima        → devuelve la próxima sesión pendiente del plan
- DELETE /plan/{plan_id}              → elimina plan y sus sesiones por_empezar
"""

from math import ceil
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.logger import get_logger
from utils.supabase_client import get_service_client
from core.plan_generator import generar_plan_de_estudio

logger = get_logger(__name__)
router = APIRouter(tags=["planes"])


class CrearPlanRequest(BaseModel):
    usuario_id: str
    asignatura_id: str
    temas_elegidos: List[str]
    fecha_examen: str          # ISO date "2026-06-15"
    atomos_por_sesion: int = 10
    lang: str = "es"
    intensity: str = "equilibrado"


@router.post("/plan/crear")
async def crear_plan(body: CrearPlanRequest):
    db = get_service_client()

    if not body.temas_elegidos:
        raise HTTPException(status_code=400, detail="Selecciona al menos un tema")

    atomos_por_sesion = max(5, min(body.atomos_por_sesion, 20))

    # Recolectar átomos
    total_atomos = 0
    atomos_detalles = []
    for tema_id in body.temas_elegidos:
        st_res = db.table("subtemas").select("id").eq("tema_id", tema_id).execute()
        for st in (st_res.data or []):
            a_res = db.table("atomos").select("id, titulo_corto").eq("subtema_id", st["id"]).execute()
            if a_res.data:
                atomos_detalles.extend(a_res.data)
                total_atomos += len(a_res.data)

    if total_atomos == 0:
        raise HTTPException(status_code=400, detail="Los temas seleccionados no tienen átomos procesados aún")

    n_sesiones_fallback = ceil(total_atomos / atomos_por_sesion)

    # Recolectar resultados de diagnóstico
    atomo_ids = [a["id"] for a in atomos_detalles]
    resultados_res = db.table("resultados").select("atomo_id, estado").eq("usuario_id", body.usuario_id).in_("atomo_id", atomo_ids).execute()
    
    diagnostic_results = {}
    for r in (resultados_res.data or []):
        diagnostic_results[r["atomo_id"]] = {"estado": r.get("estado", "rojo")}

    # Generar el plan adaptativo
    plan_data = await generar_plan_de_estudio(
        exam_date=body.fecha_examen,
        selected_atoms=atomos_detalles,
        diagnostic_results=diagnostic_results,
        intensity=body.intensity,
        lang=body.lang
    )

    is_smart_plan = bool(plan_data.get("today") or plan_data.get("next_days"))

    # Nombre del plan desde la asignatura + fecha
    asig_res = db.table("asignaturas").select("nombre").eq("id", body.asignatura_id).execute()
    asig_nombre = asig_res.data[0]["nombre"] if asig_res.data else "Asignatura"

    _meses = {
        "es": ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"],
        "en": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        "de": ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"],
    }
    _exam_word = {"es": "Examen", "en": "Exam", "de": "Prüfung"}
    try:
        fecha_obj = date.fromisoformat(body.fecha_examen)
        meses = _meses.get(body.lang, _meses["en"])
        fecha_fmt = f"{fecha_obj.day} {meses[fecha_obj.month - 1]} {fecha_obj.year}"
    except Exception:
        fecha_fmt = body.fecha_examen

    plan_nombre = f"{asig_nombre} — {_exam_word.get(body.lang, 'Exam')} {fecha_fmt}"

    # Crear plan
    n_sesiones = 0
    if is_smart_plan:
        n_sesiones = len(plan_data.get("today", [])) + sum(len(d.get("sessions", [])) for d in plan_data.get("next_days", []))
    else:
        n_sesiones = n_sesiones_fallback

    # Si por alguna razon el modelo devolvio vacio, usamos fallback logic
    strategy_mode = plan_data.get("strategy_mode", "fallback")

    plan_res = db.table("planes").insert({
        "usuario_id":       body.usuario_id,
        "asignatura_id":    body.asignatura_id,
        "nombre":           plan_nombre,
        "fecha_examen":     body.fecha_examen,
        "temas_elegidos":   body.temas_elegidos,
        "total_sesiones":   n_sesiones,
        "atomos_por_sesion": atomos_por_sesion,
        "status":           "activo",
        "tipo":             "smart" if is_smart_plan else "standard"
    }).execute()
    plan_id = plan_res.data[0]["id"]

    # Crear sesiones ligadas al plan
    if is_smart_plan:
        todas_las_sesiones_generadas = plan_data.get("today", [])
        for day in plan_data.get("next_days", []):
            todas_las_sesiones_generadas.extend(day.get("sessions", []))
            
        for ss in todas_las_sesiones_generadas:
            db.table("sesiones").insert({
                "usuario_id":            body.usuario_id,
                "asignatura_id":         body.asignatura_id,
                "temas_elegidos":        body.temas_elegidos,
                "duration_type":         "plan",
                "status":                "por_empezar",
                "current_question_index": 0,
                "plan_id":               plan_id,
                "lang":                  body.lang,
                # NUEVO: Guardar meta-datos del plan inteligente (review blocks)
                "tipo_sesion":           ss.get("type", "initial"),
                "is_review_session":     ss.get("is_review_session", False),
                "n_preguntas":           ss.get("number_of_questions", atomos_por_sesion),
            }).execute()
    else:
        for _ in range(n_sesiones_fallback):
            db.table("sesiones").insert({
                "usuario_id":            body.usuario_id,
                "asignatura_id":         body.asignatura_id,
                "temas_elegidos":        body.temas_elegidos,
                "duration_type":         "plan",
                "status":                "por_empezar",
                "current_question_index": 0,
                "plan_id":               plan_id,
                "lang":                  body.lang,
            }).execute()

    logger.info(f"Plan '{plan_nombre}' creado ({n_sesiones} sesiones, {total_atomos} átomos)")

    return {
        "plan_id":          plan_id,
        "nombre":           plan_nombre,
        "total_sesiones":   n_sesiones,
        "total_atomos":     total_atomos,
        "atomos_por_sesion": atomos_por_sesion,
        "fecha_examen":     body.fecha_examen,
    }


@router.get("/planes/usuario/{usuario_id}")
async def listar_planes_usuario(
    usuario_id: str,
    asignatura_id: Optional[str] = Query(default=None),
):
    db = get_service_client()

    q = (
        db.table("planes")
        .select("*")
        .eq("usuario_id", usuario_id)
        .order("created_at", desc=True)
    )
    if asignatura_id:
        q = q.eq("asignatura_id", asignatura_id)

    planes = q.execute().data or []

    # Enriquecer con progreso real desde sesiones
    for p in planes:
        ses_res = db.table("sesiones").select("id, status").eq("plan_id", p["id"]).execute()
        ses = ses_res.data or []
        p["sesiones_completadas"] = sum(1 for s in ses if s["status"] == "completada")
        p["sesiones_totales"]     = len(ses)

    return planes


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    """Devuelve un plan por ID."""
    db = get_service_client()
    res = db.table("planes").select("*").eq("id", plan_id).execute()
    if not res.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return res.data[0]


@router.get("/plan/{plan_id}/proxima")
async def proxima_sesion_plan(plan_id: str):
    """Devuelve la próxima sesión pendiente (por_empezar o empezada) del plan."""
    db = get_service_client()

    ses_res = (
        db.table("sesiones")
        .select("id, status, temas_elegidos, asignatura_id, current_question_index")
        .eq("plan_id", plan_id)
        .in_("status", ["por_empezar", "empezada"])
        .order("id", desc=False)
        .limit(1)
        .execute()
    )

    if not ses_res.data:
        raise HTTPException(status_code=404, detail="No hay sesiones pendientes en este plan")

    return ses_res.data[0]


@router.get("/plan/{plan_id}/sesiones")
async def sesiones_del_plan(plan_id: str):
    """Devuelve todas las sesiones del plan con número de orden y estado."""
    db = get_service_client()
    ses_res = (
        db.table("sesiones")
        .select("id, status, current_question_index, fecha_inicio, fecha_fin, is_review_session, tipo_sesion, n_preguntas")
        .eq("plan_id", plan_id)
        .order("id", desc=False)
        .execute()
    )
    sessions = ses_res.data or []
    return [
        {
            "id": s["id"],
            "numero": i + 1,
            "status": s["status"],
            "current_question_index": s.get("current_question_index", 0),
            "fecha_inicio": s.get("fecha_inicio"),
            "fecha_fin": s.get("fecha_fin"),
            "is_review_session": s.get("is_review_session", False),
            "tipo_sesion": s.get("tipo_sesion", "initial"),
            "n_preguntas": s.get("n_preguntas"),
        }
        for i, s in enumerate(sessions)
    ]


@router.delete("/plan/{plan_id}")
async def eliminar_plan(plan_id: str):
    """Elimina el plan y sus sesiones no completadas."""
    db = get_service_client()
    # Borrar solo sesiones pendientes (no destruir historial completado)
    db.table("sesiones").delete().eq("plan_id", plan_id).neq("status", "completada").execute()
    db.table("planes").delete().eq("id", plan_id).execute()
    logger.info(f"Plan {plan_id} eliminado")
    return {"ok": True}


@router.get("/plan/{plan_id}/test-atomos")
async def test_atomos_plan(plan_id: str):
    """Devuelve átomos únicos de todas las sesiones del plan para test global."""
    db = get_service_client()
    sesiones_res = (
        db.table("sesiones")
        .select("id")
        .eq("plan_id", plan_id)
        .eq("status", "completada")
        .execute()
    )
    if not sesiones_res.data:
        return []
    sesion_ids = [s["id"] for s in sesiones_res.data]
    resultados_res = (
        db.table("resultados")
        .select("atomo_id")
        .in_("sesion_id", sesion_ids)
        .execute()
    )
    if not resultados_res.data:
        return []
    atomo_ids = list({r["atomo_id"] for r in resultados_res.data})
    atomos_res = (
        db.table("atomos")
        .select("id, titulo_corto, texto_completo")
        .in_("id", atomo_ids)
        .execute()
    )
    return atomos_res.data or []
