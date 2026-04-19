"""
Endpoints de sesiones:
- POST /sesion/crear                   → crea sesión, carga átomos en memoria
- GET  /sesion/{id}/resumen            → resumen de resultados
- POST /sesion/{id}/finalizar          → marca sesión como completada, guarda skips pendientes
- GET  /sesiones/usuario/{usuario_id}  → lista sesiones del usuario (para panel de historial)
"""

from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from utils.logger import get_logger
from utils.supabase_client import get_service_client
import asyncio
from core.session_manager import (
    cargar_sesion,
    crear_sesiones_asignatura,
    preparar_atomos_priorizados,
    dividir_en_chunks,
    MAX_PREGUNTAS,
)
from core.flashcard_generator import generar_flashcard
from core.question_generator import generar_titulo_sesion

logger = get_logger(__name__)
router = APIRouter(tags=["sesiones"])


class CrearSesionRequest(BaseModel):
    usuario_id: str    = Field(..., max_length=36)
    asignatura_id: str = Field(..., max_length=36)
    temas_elegidos: List[str] = Field(..., max_length=100)
    duration_type: Literal["corta", "larga", "test", "repaso"] = "corta"
    max_atomos: Optional[int]  = Field(None, ge=1, le=30)
    n_preguntas: Optional[int] = Field(None, ge=1, le=50)
    completo: bool = False
    lang: str = Field("es", max_length=5)


@router.get("/sesiones/usuario/{usuario_id}")
async def listar_sesiones_usuario(
    usuario_id: str,
    solo_repaso: bool = False,
):
    """Lista sesiones del usuario. Por defecto excluye repaso; solo_repaso=true devuelve solo repaso."""
    db = get_service_client()

    q = (
        db.table("sesiones")
        .select("id, asignatura_id, duration_type, status, fecha_inicio, fecha_fin, current_question_index, temas_elegidos, plan_id, lang, nombre, n_preguntas, test_draft")
        .eq("usuario_id", usuario_id)
        .order("fecha_inicio", desc=True)
    )
    if solo_repaso:
        q = q.eq("duration_type", "repaso").limit(100)
    else:
        q = q.neq("duration_type", "repaso").limit(100)

    sesiones_res = q.execute()

    if not sesiones_res.data:
        return []

    asig_ids = list({s["asignatura_id"] for s in sesiones_res.data})
    asig_res = (
        db.table("asignaturas")
        .select("id, nombre, color")
        .in_("id", asig_ids)
        .execute()
    )
    asig_map = {a["id"]: a for a in (asig_res.data or [])}

    # Contar resultados por sesión — dedup por atomo_id (último estado por átomo)
    sesion_ids = [s["id"] for s in sesiones_res.data]
    resultados_res = (
        db.table("resultados")
        .select("sesion_id, atomo_id, estado")
        .in_("sesion_id", sesion_ids)
        .order("id", desc=False)  # Orden cronológico para que el último sobreescriba
        .execute()
    )
    # Guardar último estado por (sesion_id, atomo_id)
    atom_last: dict = {}
    for r in (resultados_res.data or []):
        atom_last[(r["sesion_id"], r["atomo_id"])] = r["estado"]
    # Agregar por sesión
    conteos: dict = {}
    for (sid, _aid), estado in atom_last.items():
        if sid not in conteos:
            conteos[sid] = {"verde": 0, "amarillo": 0, "rojo": 0, "total": 0}
        conteos[sid][estado] = conteos[sid].get(estado, 0) + 1
        conteos[sid]["total"] += 1

    # Obtener nombres de temas para mostrar en el historial
    all_tema_ids = list({tid for s in sesiones_res.data for tid in (s.get("temas_elegidos") or [])})
    temas_map: dict = {}
    if all_tema_ids:
        temas_res = (
            db.table("temas")
            .select("id, titulo")
            .in_("id", all_tema_ids)
            .execute()
        )
        temas_map = {t["id"]: t.get("titulo", "") for t in (temas_res.data or [])}

    sessions = []
    for s in sesiones_res.data:
        asig = asig_map.get(s["asignatura_id"], {})
        c = conteos.get(s["id"], {"verde": 0, "amarillo": 0, "rojo": 0, "total": 0})
        temas_ids = s.get("temas_elegidos") or []
        temas_nombres = [temas_map[tid] for tid in temas_ids if tid in temas_map]
        sessions.append({
            "sesion_id": s["id"],
            "asignatura_id": s["asignatura_id"],
            "asignatura_nombre": asig.get("nombre", "?"),
            "asignatura_color": asig.get("color", "#e8a030"),
            "duration_type": s.get("duration_type", "corta"),
            "status": s.get("status", "completada"),
            "fecha_inicio": s["fecha_inicio"],
            "fecha_fin": s.get("fecha_fin"),
            "current_question_index": s.get("current_question_index", 0),
            "temas_elegidos": temas_ids,
            "temas_nombres": temas_nombres,
            "conteo": c,
            "plan_id": s.get("plan_id"),
            "lang": s.get("lang", "es"),
            "nombre": s.get("nombre") or "",
            "n_preguntas": s.get("n_preguntas"),
            "has_test_draft": s.get("test_draft") is not None,
        })

    return sessions


class CrearSesionAsignaturaRequest(BaseModel):
    usuario_id: str
    asignatura_id: str
    preguntas_por_sesion: int = 10  # máx 20
    lang: str = "es"


@router.post("/sesion/crear-asignatura")
async def crear_sesiones_por_asignatura(body: CrearSesionAsignaturaRequest):
    """
    Crea automáticamente todas las sesiones necesarias para cubrir la asignatura.
    Prioriza átomos rojo → amarillo → nuevo → verde.
    Devuelve la primera sesión lista para empezar + cantidad total creadas.
    """
    db = get_service_client()
    preguntas = min(max(body.preguntas_por_sesion, 1), 20)

    chunks = await crear_sesiones_asignatura(
        asignatura_id=body.asignatura_id,
        usuario_id=body.usuario_id,
        preguntas_por_sesion=preguntas,
    )

    if not chunks:
        raise HTTPException(status_code=400, detail="Sin átomos disponibles en esta asignatura")

    sesion_ids = []
    for i, chunk in enumerate(chunks):
        tema_ids = list({a["tema_id"] for a in chunk})
        res = (
            db.table("sesiones")
            .insert({
                "usuario_id": body.usuario_id,
                "asignatura_id": body.asignatura_id,
                "temas_elegidos": tema_ids,
                "duration_type": "asignatura",
                "status": "por_empezar",
                "current_question_index": 0,
                "lang": body.lang,
            })
            .execute()
        )
        sesion_ids.append(res.data[0]["id"])

    # Precargar la primera en memoria
    primera_id = sesion_ids[0]
    primera_chunk = chunks[0]
    tema_ids_primera = list({a["tema_id"] for a in primera_chunk})
    await cargar_sesion(
        sesion_id=primera_id,
        usuario_id=body.usuario_id,
        temas_elegidos=tema_ids_primera,
        duration_type="asignatura",
        max_atomos=preguntas,
    )

    # Generar títulos para todas las sesiones en background
    async def _set_nombres_asignatura():
        for sid, chunk in zip(sesion_ids, chunks):
            textos = [a.get("texto_completo", "") for a in chunk if a.get("texto_completo")]
            nombre = await generar_titulo_sesion(textos, lang=body.lang)
            if nombre:
                db.table("sesiones").update({"nombre": nombre}).eq("id", sid).execute()

    asyncio.create_task(_set_nombres_asignatura())

    logger.info(
        f"Asignatura {body.asignatura_id}: {len(sesion_ids)} sesiones creadas "
        f"({preguntas} preguntas c/u)"
    )

    return {
        "sesion_id": primera_id,
        "n_atomos": len(primera_chunk),
        "sesiones_creadas": len(sesion_ids),
        "sesiones_pendientes": len(sesion_ids) - 1,
        "preguntas_por_sesion": preguntas,
        "duration_type": "asignatura",
    }


@router.post("/sesion/crear")
async def crear_sesion(body: CrearSesionRequest):
    db = get_service_client()
    logger.info(
        f"Crear sesión: usuario={body.usuario_id} "
        f"asignatura={body.asignatura_id} tipo={body.duration_type} "
        f"completo={body.completo}"
    )

    if not body.temas_elegidos:
        raise HTTPException(status_code=400, detail="Debes elegir al menos un tema")

    # ══════════════════════════════════════════════════════════════════
    # MODO COMPLETO: todos los átomos → dividir en partes
    # ══════════════════════════════════════════════════════════════════
    if body.completo:
        # Límite por parte
        if body.max_atomos or body.n_preguntas:
            preguntas_por_sesion = min(body.max_atomos or body.n_preguntas, MAX_PREGUNTAS)
        elif body.duration_type == "test":
            preguntas_por_sesion = body.n_preguntas or 10
        else:
            preguntas_por_sesion = 10  # chunks de 10

        atomos_priorizados = await preparar_atomos_priorizados(
            temas_elegidos=body.temas_elegidos,
            usuario_id=body.usuario_id,
        )
        if not atomos_priorizados:
            raise HTTPException(status_code=400, detail="Sin átomos disponibles")

        chunks = dividir_en_chunks(atomos_priorizados, preguntas_por_sesion)
        n_partes = len(chunks)

        # Si hay 2+ partes → crear un plan real que las agrupe
        plan_id = None
        if n_partes > 1:
            plan_res = db.table("planes").insert({
                "usuario_id": body.usuario_id,
                "asignatura_id": body.asignatura_id,
                "nombre": "",  # se genera en background
                "temas_elegidos": body.temas_elegidos,
                "total_sesiones": n_partes,
                "atomos_por_sesion": preguntas_por_sesion,
                "status": "activo",
                "lang": body.lang,
            }).execute()
            plan_id = plan_res.data[0]["id"]
            logger.info(f"Plan COMPLETO creado: {plan_id} — {n_partes} sesiones")

        sesion_ids = []
        for i, chunk in enumerate(chunks):
            tema_ids_chunk = list({a["tema_id"] for a in chunk})
            insert_data = {
                "usuario_id": body.usuario_id,
                "asignatura_id": body.asignatura_id,
                "temas_elegidos": tema_ids_chunk,
                "duration_type": "plan" if plan_id else body.duration_type,
                "status": "por_empezar",
                "current_question_index": 0,
                "lang": body.lang,
                "n_preguntas": len(chunk),
                **({"plan_id": plan_id} if plan_id else {}),
            }
            res = db.table("sesiones").insert(insert_data).execute()
            sesion_ids.append(res.data[0]["id"])

        # Pre-cargar la primera sesión
        primera_id = sesion_ids[0]
        primera_chunk = chunks[0]
        tema_ids_primera = list({a["tema_id"] for a in primera_chunk})
        sesion = await cargar_sesion(
            sesion_id=primera_id,
            usuario_id=body.usuario_id,
            temas_elegidos=tema_ids_primera,
            duration_type="plan" if plan_id else body.duration_type,
            max_atomos=len(primera_chunk),
        )

        logger.info(
            f"Sesión COMPLETA {primera_id} — {len(sesion.atomos)} átomos "
            f"({body.duration_type}) [{n_partes} parte(s)]"
        )

        # Generar nombre del plan + títulos de sesiones en background
        async def _set_nombres():
            # Nombre del plan: usar todos los textos del primer chunk
            if plan_id:
                textos_plan = [a.get("texto_completo", "") for a in chunks[0] if a.get("texto_completo")]
                nombre_plan = await generar_titulo_sesion(textos_plan, lang=body.lang)
                if nombre_plan:
                    db.table("planes").update({"nombre": nombre_plan}).eq("id", plan_id).execute()
            for i, (sid, chunk) in enumerate(zip(sesion_ids, chunks)):
                textos = [a.get("texto_completo", "") for a in chunk if a.get("texto_completo")]
                nombre = await generar_titulo_sesion(textos, lang=body.lang)
                if nombre and n_partes > 1:
                    nombre = f"{nombre} ({i + 1}/{n_partes})"
                if nombre:
                    db.table("sesiones").update({"nombre": nombre}).eq("id", sid).execute()
        asyncio.create_task(_set_nombres())

        return {
            "sesion_id": primera_id,
            "n_atomos": len(sesion.atomos),
            "duration_type": "plan" if plan_id else body.duration_type,
            "temas_elegidos": body.temas_elegidos,
            "sesiones_creadas": n_partes,
            "sesiones_pendientes": n_partes - 1,
            "sesion_ids": sesion_ids,
            "plan_id": plan_id,
        }

    # ══════════════════════════════════════════════════════════════════
    # MODO NORMAL: sesión única con subconjunto de átomos
    # ══════════════════════════════════════════════════════════════════
    res = (
        db.table("sesiones")
        .insert({
            "usuario_id": body.usuario_id,
            "asignatura_id": body.asignatura_id,
            "temas_elegidos": body.temas_elegidos,
            "duration_type": body.duration_type,
            "status": "por_empezar",
            "current_question_index": 0,
            "lang": body.lang,
            **({"n_preguntas": body.n_preguntas} if body.n_preguntas else {}),
        })
        .execute()
    )
    sesion_id = res.data[0]["id"]

    sesion = await cargar_sesion(
        sesion_id=sesion_id,
        usuario_id=body.usuario_id,
        temas_elegidos=body.temas_elegidos,
        duration_type=body.duration_type,
        max_atomos=body.max_atomos or body.n_preguntas,
    )

    logger.info(f"Sesión {sesion_id} creada — {len(sesion.atomos)} átomos ({body.duration_type})")

    # Generar título en background
    async def _set_nombre():
        textos = [a.texto_completo for a in sesion.atomos if a.texto_completo]
        nombre = await generar_titulo_sesion(textos, lang=body.lang)
        if nombre:
            db.table("sesiones").update({"nombre": nombre}).eq("id", sesion_id).execute()
    asyncio.create_task(_set_nombre())

    return {
        "sesion_id": sesion_id,
        "n_atomos": len(sesion.atomos),
        "duration_type": body.duration_type,
        "temas_elegidos": body.temas_elegidos,
        "sesiones_creadas": 1,
        "sesiones_pendientes": 0,
        "sesion_ids": [sesion_id],
    }


@router.get("/sesion/{sesion_id}/resumen")
async def resumen_sesion(sesion_id: str):
    db = get_service_client()

    sesion_res = db.table("sesiones").select("*").eq("id", sesion_id).execute()
    if not sesion_res.data:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    sesion = sesion_res.data[0]

    resultados_res = (
        db.table("resultados")
        .select("estado, similitud_coseno")
        .eq("sesion_id", sesion_id)
        .execute()
    )
    resultados = resultados_res.data or []

    conteo = {"verde": 0, "amarillo": 0, "rojo": 0}
    similitudes = []
    for r in resultados:
        conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1
        if r["similitud_coseno"] is not None:
            similitudes.append(r["similitud_coseno"])

    promedio_similitud = round(sum(similitudes) / len(similitudes), 3) if similitudes else None

    return {
        "sesion_id": sesion_id,
        "fecha_inicio": sesion["fecha_inicio"],
        "fecha_fin": sesion["fecha_fin"],
        "duracion_segundos": sesion["duracion_segundos"],
        "duration_type": sesion.get("duration_type", "corta"),
        "status": sesion.get("status", "completada"),
        "total_evaluados": len(resultados),
        "conteo": conteo,
        "promedio_similitud": promedio_similitud,
    }


@router.get("/sesion/{sesion_id}/fallos")
async def fallos_sesion(sesion_id: str):
    """Devuelve preguntas falladas (rojo) con su flashcard para revisión."""
    db = get_service_client()

    resultados_res = (
        db.table("resultados")
        .select("atomo_id, pregunta, respuesta_usuario, similitud_coseno")
        .eq("sesion_id", sesion_id)
        .eq("estado", "rojo")
        .execute()
    )
    if not resultados_res.data:
        return []

    atomo_ids = [r["atomo_id"] for r in resultados_res.data]

    atomos_res = (
        db.table("atomos")
        .select("id, titulo_corto, texto_completo")
        .in_("id", atomo_ids)
        .execute()
    )
    atomos_map = {a["id"]: a for a in (atomos_res.data or [])}

    flashcards_res = (
        db.table("flashcards_history")
        .select("atomo_id, concepto, error_cometido, analogia_generada")
        .eq("session_id", sesion_id)
        .in_("atomo_id", atomo_ids)
        .execute()
    )
    flashcards_map = {f["atomo_id"]: f for f in (flashcards_res.data or [])}

    fallos = []
    for r in resultados_res.data:
        aid = r["atomo_id"]
        atomo = atomos_map.get(aid, {})
        flashcard = flashcards_map.get(aid)
        fallos.append({
            "atomo_id": aid,
            "titulo": atomo.get("titulo_corto", "?"),
            "pregunta": r.get("pregunta") or atomo.get("titulo_corto", ""),
            "respuesta_usuario": r.get("respuesta_usuario", ""),
            "similitud": round(r.get("similitud_coseno") or 0, 3),
            "texto_completo": atomo.get("texto_completo", ""),
            "flashcard": flashcard,
        })

    return fallos


@router.get("/sesion/{sesion_id}/revision")
async def revision_sesion(sesion_id: str):
    """Devuelve TODOS los átomos respondidos (verde, amarillo, rojo) deduplicados por átomo."""
    db = get_service_client()

    resultados_res = (
        db.table("resultados")
        .select("atomo_id, pregunta, respuesta_usuario, estado, similitud_coseno")
        .eq("sesion_id", sesion_id)
        .order("id", desc=False)
        .execute()
    )
    if not resultados_res.data:
        return []

    # Dedup: keep last result per atomo_id
    atom_last: dict = {}
    for r in resultados_res.data:
        atom_last[r["atomo_id"]] = r

    if not atom_last:
        return []

    atomo_ids = list(atom_last.keys())

    atomos_res = (
        db.table("atomos")
        .select("id, titulo_corto, texto_completo")
        .in_("id", atomo_ids)
        .execute()
    )
    atomos_map = {a["id"]: a for a in (atomos_res.data or [])}

    flashcards_res = (
        db.table("flashcards_history")
        .select("atomo_id, concepto, error_cometido, analogia_generada")
        .eq("session_id", sesion_id)
        .in_("atomo_id", atomo_ids)
        .execute()
    )
    flashcards_map = {f["atomo_id"]: f for f in (flashcards_res.data or [])}

    revision = []
    for aid, r in atom_last.items():
        atomo = atomos_map.get(aid, {})
        flashcard = flashcards_map.get(aid)
        revision.append({
            "atomo_id": aid,
            "titulo": atomo.get("titulo_corto", "?"),
            "pregunta": r.get("pregunta") or atomo.get("titulo_corto", ""),
            "respuesta_usuario": r.get("respuesta_usuario", ""),
            "estado": r.get("estado", "rojo"),
            "similitud": round(r.get("similitud_coseno") or 0, 3),
            "texto_completo": atomo.get("texto_completo", ""),
            "flashcard": flashcard,
        })

    return revision


@router.patch("/sesion/{sesion_id}/test-draft")
async def save_test_draft(sesion_id: str, request: Request):
    """Guarda (o borra si body=null) el borrador del test en curso."""
    body = await request.json()
    db = get_service_client()
    db.table("sesiones").update({"test_draft": body}).eq("id", sesion_id).execute()
    return {"ok": True}


@router.get("/sesion/{sesion_id}/test-draft")
async def get_test_draft(sesion_id: str):
    """Devuelve el borrador del test guardado, o None si no existe."""
    db = get_service_client()
    res = db.table("sesiones").select("test_draft").eq("id", sesion_id).execute()
    if not res.data:
        return None
    return res.data[0].get("test_draft")


@router.get("/sesion/{sesion_id}/test-atomos")
async def test_atomos_sesion(sesion_id: str):
    """Devuelve átomos únicos de la sesión para generar test de consolidación."""
    db = get_service_client()
    resultados_res = (
        db.table("resultados")
        .select("atomo_id")
        .eq("sesion_id", sesion_id)
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


@router.delete("/sesion/{sesion_id}")
async def eliminar_sesion(sesion_id: str):
    """Elimina una sesión y todos sus resultados/flashcards asociados."""
    db = get_service_client()
    db.table("flashcards_history").delete().eq("session_id", sesion_id).execute()
    db.table("resultados").delete().eq("sesion_id", sesion_id).execute()
    db.table("sesiones").delete().eq("id", sesion_id).execute()
    logger.info(f"Sesión {sesion_id} eliminada")
    return {"ok": True}


@router.post("/sesion/{sesion_id}/finalizar")
async def finalizar_sesion(sesion_id: str):
    """
    Marca la sesión como completada.
    Cualquier átomo saltado (skip) se guarda en flashcards_history si no tiene resultado.
    """
    db = get_service_client()

    sesion_res = db.table("sesiones").select("*").eq("id", sesion_id).execute()
    if not sesion_res.data:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    sesion = sesion_res.data[0]

    if sesion.get("status") == "completada":
        return {"ok": True, "mensaje": "Sesión ya estaba completada"}

    # Átomos que tenían que responderse
    temas = sesion["temas_elegidos"]
    atomos_res = (
        db.table("atomos")
        .select("id, titulo_corto, texto_completo")
        .in_("tema_id", temas)
        .execute()
    )
    todos_ids = {a["id"]: a for a in (atomos_res.data or [])}

    # Átomos que ya tienen resultado
    respondidos_res = (
        db.table("resultados")
        .select("atomo_id")
        .eq("sesion_id", sesion_id)
        .execute()
    )
    respondidos_ids = {r["atomo_id"] for r in (respondidos_res.data or [])}

    # Skips (átomos sin respuesta) → guardar como rojo + flashcards_history
    skips = [a for aid, a in todos_ids.items() if aid not in respondidos_ids]
    for atomo in skips:
        db.table("resultados").insert({
            "sesion_id": sesion_id,
            "atomo_id": atomo["id"],
            "estado": "rojo",
            "respuesta_usuario": "[saltado]",
            "similitud_coseno": 0.0,
        }).execute()
        db.table("flashcards_history").insert({
            "session_id": sesion_id,
            "atomo_id": atomo["id"],
            "concepto": atomo["titulo_corto"],
            "error_cometido": "Pregunta saltada sin responder",
            "analogia_generada": atomo["texto_completo"][:300],
        }).execute()

    fecha_fin = datetime.utcnow().isoformat()
    db.table("sesiones").update({
        "fecha_fin": fecha_fin,
        "status": "completada",
    }).eq("id", sesion_id).execute()

    logger.info(f"[{sesion_id}] Finalizada — {len(skips)} skips guardados")
    return {"ok": True, "skips_guardados": len(skips)}
