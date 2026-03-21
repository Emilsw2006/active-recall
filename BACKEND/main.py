"""
Active Recall Backend — FastAPI
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from postgrest.exceptions import APIError

from api.routes.auth import router as auth_router
from api.routes.asignaturas import router as asignaturas_router
from api.routes.documentos import router as documentos_router
from api.routes.atomos import router as atomos_router
from api.routes.sesiones import router as sesiones_router
from api.routes.flashcards import router as flashcards_router
from api.routes.planes import router as planes_router
from api.routes.tests import router as tests_router
from api.websocket import router as ws_router
from utils.logger import get_logger

logger = get_logger(__name__)


async def _session_cleanup_loop():
    """Periodic cleanup of stale in-memory sessions (every 5 min)."""
    import asyncio
    from core.session_manager import cleanup_stale_sessions
    while True:
        await asyncio.sleep(300)  # 5 minutos
        try:
            cleanup_stale_sessions()
        except Exception as e:
            logger.error(f"Error en session cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    logger.info("Active Recall API iniciada — cargando modelo de embeddings...")
    from core.vectorizer import get_model
    get_model()
    logger.info("Modelo listo. Servidor operativo.")
    # Periodic session cleanup task
    cleanup_task = asyncio.create_task(_session_cleanup_loop())
    yield
    cleanup_task.cancel()
    logger.info("Active Recall API apagada")


app = FastAPI(
    title="Active Recall API",
    description="Backend para la app de estudio con Active Recall y voz",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Captura errores de Supabase/PostgREST y los devuelve como 400 en vez de 500
@app.exception_handler(APIError)
async def supabase_api_error_handler(request: Request, exc: APIError):
    code = exc.details.get("code", "") if isinstance(exc.details, dict) else ""
    status = 400 if code in ("22P02", "23503", "23505") else 500
    msg = exc.message if hasattr(exc, "message") else str(exc)
    logger.error(f"Supabase APIError [{code}]: {msg} — {request.url}")
    return JSONResponse(status_code=status, content={"detail": msg})


# Routers
app.include_router(auth_router)
app.include_router(asignaturas_router)
app.include_router(documentos_router)
app.include_router(atomos_router)
app.include_router(sesiones_router)
app.include_router(flashcards_router)
app.include_router(planes_router)
app.include_router(tests_router)
app.include_router(ws_router)


FRONTEND_DIR = Path(__file__).parent.parent / "TEST-APP"

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/tts/preview")
async def tts_preview(voice: str = "ef_dora"):
    """Genera un audio corto de muestra para previsualizar la voz."""
    from core.tts import texto_a_audio_base64, get_last_audio_format
    frases = {
        "ef_dora":  "Hola, soy Dora. ¿Empezamos a estudiar?",
        "em_alex":  "Hola, soy Alex. Vamos a repasar juntos.",
        "em_santa": "Hola, soy Santa. Prepárate para aprender.",
    }
    texto = frases.get(voice, "Hola, esta es mi voz.")
    b64 = await texto_a_audio_base64(texto, voz=voice)
    fmt = get_last_audio_format()
    return {"audio_b64": b64, "format": fmt}


@app.get("/auth/update-nombre")
async def update_nombre_get(usuario_id: str, nombre: str):
    """Actualiza el nombre del usuario."""
    from utils.supabase_client import get_service_client
    db = get_service_client()
    db.table("usuarios").update({"nombre": nombre}).eq("id", usuario_id).execute()
    return {"ok": True, "nombre": nombre}


@app.get("/auth/update-mundo-analogias")
async def update_mundo_analogias(usuario_id: str, mundo: str):
    """Actualiza el mundo de analogías del usuario."""
    from utils.supabase_client import get_service_client
    db = get_service_client()
    db.table("usuarios").update({"mundo_analogias": mundo}).eq("id", usuario_id).execute()
    return {"ok": True, "mundo_analogias": mundo}


@app.get("/notificaciones/{usuario_id}")
async def get_notificaciones(usuario_id: str):
    """Genera notificaciones inteligentes para la home del usuario."""
    from datetime import date, timedelta
    from utils.supabase_client import get_service_client
    db = get_service_client()
    notifs = []
    hoy = date.today()

    # 1. Sesiones a medias
    empezadas = (
        db.table("sesiones")
        .select("id, asignatura_id, current_question_index")
        .eq("usuario_id", usuario_id)
        .eq("status", "empezada")
        .execute()
    )
    if empezadas.data:
        asig_ids = list({s["asignatura_id"] for s in empezadas.data})
        asig_res = db.table("asignaturas").select("id, nombre").in_("id", asig_ids).execute()
        asig_map = {a["id"]: a["nombre"] for a in (asig_res.data or [])}
        for s in empezadas.data:
            nombre = asig_map.get(s["asignatura_id"], "Asignatura")
            idx = s.get("current_question_index") or 0
            notifs.append({
                "tipo": "sesion_pendiente",
                "prioridad": 1,
                "titulo": "Sesión a medias",
                "mensaje": f"{nombre} — pregunta {idx + 1} en curso",
                "accion": {"tipo": "reanudar_sesion", "sesion_id": s["id"], "asignatura_id": s["asignatura_id"], "asignatura_nombre": nombre},
                "icono": "📝",
                "color": "amber",
            })

    # 2. Planes activos
    planes = (
        db.table("planes")
        .select("id, nombre, fecha_examen, asignatura_id")
        .eq("usuario_id", usuario_id)
        .eq("status", "activo")
        .execute()
    )
    for p in (planes.data or []):
        ses_res = db.table("sesiones").select("id, status").eq("plan_id", p["id"]).execute()
        ses = ses_res.data or []
        completadas = sum(1 for s in ses if s["status"] == "completada")
        total = len(ses)
        pendientes = total - completadas
        if pendientes <= 0:
            continue
        try:
            fecha_ex = date.fromisoformat(p["fecha_examen"])
            dias = (fecha_ex - hoy).days
        except Exception:
            dias = 999

        if dias <= 7:
            notifs.append({
                "tipo": "examen_cerca",
                "prioridad": 2,
                "titulo": "Examen próximo",
                "mensaje": f"{p['nombre']} en {dias} día{'s' if dias != 1 else ''} — te faltan {pendientes} sesiones",
                "accion": {"tipo": "continuar_plan", "plan_id": p["id"]},
                "icono": "🔥",
                "color": "red",
            })
        else:
            notifs.append({
                "tipo": "plan_progreso",
                "prioridad": 3,
                "titulo": p["nombre"],
                "mensaje": f"{completadas}/{total} sesiones completadas",
                "accion": {"tipo": "continuar_plan", "plan_id": p["id"]},
                "icono": "📚",
                "color": "blue",
            })

    # 3. Flashcards problemáticas
    fc_res = (
        db.table("flashcards")
        .select("id", count="exact")
        .eq("usuario_id", usuario_id)
        .gte("veces_fallada", 2)
        .execute()
    )
    fc_count = fc_res.count or 0
    if fc_count > 0:
        notifs.append({
            "tipo": "errores_pendientes",
            "prioridad": 4,
            "titulo": "Conceptos difíciles",
            "mensaje": f"{fc_count} concepto{'s' if fc_count != 1 else ''} que sigues fallando",
            "accion": {"tipo": "ver_errores"},
            "icono": "⚠️",
            "color": "amber",
        })

    # 4. Racha de estudio + tiempo sin estudiar
    sesiones_comp = (
        db.table("sesiones")
        .select("fecha_fin")
        .eq("usuario_id", usuario_id)
        .eq("status", "completada")
        .order("fecha_fin", desc=True)
        .limit(30)
        .execute()
    )
    if sesiones_comp.data:
        fechas = set()
        for s in sesiones_comp.data:
            if s.get("fecha_fin"):
                try:
                    fechas.add(date.fromisoformat(s["fecha_fin"][:10]))
                except Exception:
                    pass
        # Racha
        racha = 0
        dia = hoy
        while dia in fechas:
            racha += 1
            dia -= timedelta(days=1)
        if racha >= 3:
            notifs.append({
                "tipo": "racha",
                "prioridad": 5,
                "titulo": "¡Buena racha!",
                "mensaje": f"Llevas {racha} días seguidos estudiando",
                "accion": {},
                "icono": "🔥",
                "color": "green",
            })
        # Tiempo sin estudiar
        ultima_fecha = max(fechas) if fechas else None
        if ultima_fecha:
            dias_sin = (hoy - ultima_fecha).days
            if dias_sin >= 2 and racha == 0:
                notifs.append({
                    "tipo": "sin_estudiar",
                    "prioridad": 6,
                    "titulo": "Te echamos de menos",
                    "mensaje": f"Llevas {dias_sin} días sin estudiar",
                    "accion": {"tipo": "iniciar_sesion"},
                    "icono": "⏰",
                    "color": "amber",
                })
    else:
        # Nunca ha estudiado
        notifs.append({
            "tipo": "sin_estudiar",
            "prioridad": 6,
            "titulo": "¡Empieza a estudiar!",
            "mensaje": "Haz tu primera sesión de repaso",
            "accion": {"tipo": "iniciar_sesion"},
            "icono": "🚀",
            "color": "blue",
        })

    notifs.sort(key=lambda n: n["prioridad"])
    return notifs


@app.get("/app", response_class=FileResponse)
async def serve_app():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/style.css", response_class=FileResponse)
async def serve_style():
    return FileResponse(FRONTEND_DIR / "style.css")

@app.get("/app.js", response_class=FileResponse)
async def serve_js():
    return FileResponse(FRONTEND_DIR / "app.js")

@app.get("/i18n.js", response_class=FileResponse)
async def serve_i18n():
    return FileResponse(FRONTEND_DIR / "i18n.js")

@app.get("/")
async def root():
    return {"status": "ok", "mensaje": "Active Recall API funcionando"}


@app.get("/health")
async def health():
    from core.vectorizer import _model
    from core.session_manager import active_session_count
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "active_sessions": active_session_count(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
