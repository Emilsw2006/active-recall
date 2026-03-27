"""
Endpoints de tipo test:
- POST /test/generar         → genera preguntas con Gemini a partir de átomos
- POST /test/guardar         → guarda resultado en tabla tests
- GET  /tests/usuario/{uid} → historial de tests del usuario
- GET  /test/{id}/revision  → preguntas + respuestas del usuario para revisar
"""

import asyncio
import traceback
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.test_generator import generar_preguntas_test
from core.question_generator import generar_titulo_sesion
from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)
router = APIRouter(tags=["tests"])


class GenerarTestRequest(BaseModel):
    usuario_id: str
    asignatura_id: Optional[str] = None
    sesion_id: Optional[str] = None
    plan_id: Optional[str] = None
    n_preguntas: int = 6
    lang: str = "es"


class GuardarTestRequest(BaseModel):
    usuario_id: str
    asignatura_id: Optional[str] = None
    sesion_id: Optional[str] = None
    plan_id: Optional[str] = None
    preguntas: list
    respuestas: list
    puntuacion: int
    total: int
    tipo: str = "sesion"
    lang: str = "es"


@router.post("/test/generar")
async def generar_test(body: GenerarTestRequest):
    """Obtiene átomos de la sesión/plan y genera preguntas con Gemini."""
    db = get_service_client()

    # Fetch atoms from sesion or plan
    atomo_ids = set()

    if body.sesion_id:
        res = await asyncio.to_thread(
            lambda: db.table("resultados")
            .select("atomo_id")
            .eq("sesion_id", body.sesion_id)
            .execute()
        )
        atomo_ids = {r["atomo_id"] for r in (res.data or [])}

    elif body.plan_id:
        ses_res = await asyncio.to_thread(
            lambda: db.table("sesiones")
            .select("id")
            .eq("plan_id", body.plan_id)
            .eq("status", "completada")
            .execute()
        )
        ses_ids = [s["id"] for s in (ses_res.data or [])]
        if ses_ids:
            res = await asyncio.to_thread(
                lambda: db.table("resultados")
                .select("atomo_id")
                .in_("sesion_id", ses_ids)
                .execute()
            )
            atomo_ids = {r["atomo_id"] for r in (res.data or [])}

    import random

    if atomo_ids:
        atomos_res = await asyncio.to_thread(
            lambda: db.table("atomos")
            .select("id, titulo_corto, texto_completo")
            .in_("id", list(atomo_ids))
            .execute()
        )
        atomos = atomos_res.data or []
    elif body.asignatura_id:
        # Fallback: generate test directly from all atoms in the subject
        atomos_res = await asyncio.to_thread(
            lambda: db.table("atomos")
            .select("id, titulo_corto, texto_completo")
            .eq("asignatura_id", body.asignatura_id)
            .execute()
        )
        atomos = atomos_res.data or []
    else:
        raise HTTPException(status_code=404, detail="No hay átomos para generar el test")

    if not atomos:
        raise HTTPException(status_code=404, detail="Átomos no encontrados")

    # Shuffle and limit
    random.shuffle(atomos)
    n = min(body.n_preguntas, len(atomos), 12)
    atomos = atomos[:n]

    try:
        preguntas = await generar_preguntas_test(atomos, n=n, lang=body.lang)
    except Exception as e:
        logger.error(f"Error generando test:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generando preguntas: {type(e).__name__}: {e}")

    if not preguntas:
        raise HTTPException(status_code=500, detail="Gemini no generó preguntas válidas")

    return preguntas


@router.post("/test/guardar")
async def guardar_test(body: GuardarTestRequest):
    """Guarda el resultado de un test en la base de datos."""
    db = get_service_client()
    data = {
        "usuario_id": body.usuario_id,
        "asignatura_id": body.asignatura_id,
        "sesion_id": body.sesion_id,
        "plan_id": body.plan_id,
        "preguntas": body.preguntas,
        "respuestas": body.respuestas,
        "puntuacion": body.puntuacion,
        "total": body.total,
        "tipo": body.tipo,
        "lang": body.lang,
    }
    res = await asyncio.to_thread(lambda: db.table("tests").insert(data).execute())
    if not res.data:
        raise HTTPException(status_code=500, detail="Error guardando test")
    test_id = res.data[0]["id"]

    # Generar título descriptivo en background a partir de las preguntas del test
    async def _set_nombre_test():
        textos = [p.get("pregunta", "") for p in (body.preguntas or []) if p.get("pregunta")]
        nombre = await generar_titulo_sesion(textos, lang=body.lang)
        if nombre:
            await asyncio.to_thread(lambda: db.table("tests").update({"nombre": nombre}).eq("id", test_id).execute())

    asyncio.create_task(_set_nombre_test())

    return res.data[0]


@router.get("/tests/usuario/{usuario_id}")
async def listar_tests_usuario(usuario_id: str):
    """Lista todos los tests del usuario con info de asignatura."""
    db = get_service_client()

    tests_res = await asyncio.to_thread(
        lambda: db.table("tests")
        .select("id, asignatura_id, sesion_id, plan_id, puntuacion, total, tipo, fecha, lang, nombre")
        .eq("usuario_id", usuario_id)
        .order("fecha", desc=True)
        .limit(50)
        .execute()
    )
    tests = tests_res.data or []
    if not tests:
        return []

    asig_ids = list({t["asignatura_id"] for t in tests if t.get("asignatura_id")})
    asig_map = {}
    if asig_ids:
        asig_res = await asyncio.to_thread(
            lambda: db.table("asignaturas").select("id, nombre, color").in_("id", asig_ids).execute()
        )
        asig_map = {a["id"]: a for a in (asig_res.data or [])}

    result = []
    for t in tests:
        asig = asig_map.get(t.get("asignatura_id"), {})
        result.append({
            "test_id": t["id"],
            "asignatura_id": t.get("asignatura_id"),
            "asignatura_nombre": asig.get("nombre", "?"),
            "asignatura_color": asig.get("color", "#4f7eff"),
            "sesion_id": t.get("sesion_id"),
            "plan_id": t.get("plan_id"),
            "puntuacion": t["puntuacion"],
            "total": t["total"],
            "tipo": t["tipo"],
            "fecha": t["fecha"],
            "lang": t.get("lang", "es"),
            "nombre": t.get("nombre") or "",
        })

    return result


@router.get("/test/{test_id}/revision")
async def revision_test(test_id: str):
    """Devuelve las preguntas y respuestas del usuario para revisar un test."""
    db = get_service_client()
    res = await asyncio.to_thread(
        lambda: db.table("tests")
        .select("preguntas, respuestas, puntuacion, total, fecha")
        .eq("id", test_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Test no encontrado")
    return res.data[0]
