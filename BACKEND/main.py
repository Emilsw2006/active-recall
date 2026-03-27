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
async def tts_preview(voice: str = "ef_dora", lang: str = "es"):
    """Genera un audio corto de muestra para previsualizar la voz."""
    from core.tts import texto_a_audio_base64, get_last_audio_format
    frases = {
        # Kokoro — Spanish
        "ef_dora":  "Hola, soy Dora. ¿Empezamos a estudiar?",
        "em_alex":  "Hola, soy Álex. ¿Listo para aprender?",
        "em_santa": "Hola, soy Santa. Prepárate para aprender.",
        # Kokoro — English
        "af_sarah":   "Hi, I'm Sarah. Let's start studying!",
        "af_bella":   "Hi, I'm Bella. Ready to learn?",
        "am_michael": "Hi, I'm Michael. Let's review together!",
        # Edge — German
        "de-DE-KatjaNeural":  "Hallo, ich bin Katja. Lass uns lernen!",
        "de-DE-AmalaNeural":  "Hallo, ich bin Amala. Bereit zum Lernen?",
        "de-DE-ConradNeural": "Hallo, ich bin Conrad. Los geht's!",
    }
    texto = frases.get(voice, "Hola, soy tu tutor. ¿Empezamos?")
    b64 = await texto_a_audio_base64(texto, voz=voice, lang=lang)
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
async def get_notificaciones(usuario_id: str, lang: str = "es"):
    """Genera notificaciones inteligentes para la home del usuario."""
    from datetime import date, timedelta
    from utils.supabase_client import get_service_client
    db = get_service_client()
    notifs = []
    hoy = date.today()

    def _t(key: str, **kw) -> str:
        """Micro-traductor para notificaciones."""
        _strings = {
            "ses_title":   {"es": "Sesión a medias",        "en": "Session in progress",      "de": "Angefangene Sitzung"},
            "ses_msg":     {"es": "{nombre} — pregunta {n} en curso", "en": "{nombre} — question {n} in progress", "de": "{nombre} — Frage {n} läuft"},
            "exam_title":  {"es": "Examen próximo",          "en": "Exam coming up",           "de": "Prüfung bald"},
            "exam_msg":    {"es": "{nombre} en {dias} día{s} — te faltan {n} sesiones",
                            "en": "{nombre} in {dias} day{s} — {n} sessions left",
                            "de": "{nombre} in {dias} Tag{s} — {n} Sitzungen fehlen"},
            "plan_msg":    {"es": "{c}/{t} sesiones completadas", "en": "{c}/{t} sessions completed", "de": "{c}/{t} Sitzungen abgeschlossen"},
            "hard_title":  {"es": "Conceptos difíciles",     "en": "Difficult concepts",       "de": "Schwierige Konzepte"},
            "hard_msg":    {"es": "{n} concepto{s} que sigues fallando",
                            "en": "{n} concept{s} you keep getting wrong",
                            "de": "{n} Konzept{s}, die du noch falsch machst"},
            "streak_title":{"es": "¡Buena racha!",           "en": "Great streak!",            "de": "Tolle Serie!"},
            "streak_msg":  {"es": "Llevas {n} días seguidos estudiando",
                            "en": "You've studied {n} days in a row",
                            "de": "Du lernst seit {n} Tagen in Folge"},
            "miss_title":  {"es": "Te echamos de menos",     "en": "We miss you",              "de": "Wir vermissen dich"},
            "miss_msg":    {"es": "Llevas {n} días sin estudiar",
                            "en": "You haven't studied in {n} days",
                            "de": "Du hast seit {n} Tagen nicht gelernt"},
            "start_title": {"es": "¡Empieza a estudiar!",    "en": "Start studying!",          "de": "Fang an zu lernen!"},
            "start_msg":   {"es": "Haz tu primera sesión de repaso",
                            "en": "Do your first review session",
                            "de": "Mache deine erste Lernsitzung"},
        }
        tmpl = _strings.get(key, {}).get(lang) or _strings.get(key, {}).get("es", key)
        return tmpl.format(**kw)

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
                "titulo": _t("ses_title"),
                "mensaje": _t("ses_msg", nombre=nombre, n=idx + 1),
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
                "titulo": _t("exam_title"),
                "mensaje": _t("exam_msg", nombre=p["nombre"], dias=dias, s="s" if dias != 1 else "", n=pendientes),
                "accion": {"tipo": "continuar_plan", "plan_id": p["id"]},
                "icono": "🔥",
                "color": "red",
            })
        else:
            notifs.append({
                "tipo": "plan_progreso",
                "prioridad": 3,
                "titulo": p["nombre"],
                "mensaje": _t("plan_msg", c=completadas, t=total),
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
            "titulo": _t("hard_title"),
            "mensaje": _t("hard_msg", n=fc_count, s="s" if fc_count != 1 else ""),
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
                "titulo": _t("streak_title"),
                "mensaje": _t("streak_msg", n=racha),
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
                    "titulo": _t("miss_title"),
                    "mensaje": _t("miss_msg", n=dias_sin),
                    "accion": {"tipo": "iniciar_sesion"},
                    "icono": "⏰",
                    "color": "amber",
                })
    else:
        # Nunca ha estudiado
        notifs.append({
            "tipo": "sin_estudiar",
            "prioridad": 6,
            "titulo": _t("start_title"),
            "mensaje": _t("start_msg"),
            "accion": {"tipo": "iniciar_sesion"},
            "icono": "🚀",
            "color": "blue",
        })

    notifs.sort(key=lambda n: n["prioridad"])
    return notifs


@app.get("/app", response_class=FileResponse)
async def serve_app():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/app/", response_class=FileResponse)
async def serve_app_slash():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/app/{filepath:path}")
async def serve_app_files(filepath: str):
    """Serve any file under /app/ from TEST-APP directory."""
    file_path = FRONTEND_DIR / filepath
    if file_path.is_file():
        media_types = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".webmanifest": "application/manifest+json",
        }
        suffix = file_path.suffix.lower()
        media_type = media_types.get(suffix, "application/octet-stream")
        headers = {}
        if filepath == "sw.js":
            headers["Service-Worker-Allowed"] = "/app"
        return FileResponse(file_path, media_type=media_type, headers=headers)
    return FileResponse(FRONTEND_DIR / "index.html")

# Serve key PWA files at root (relative URLs from /app resolve here)
@app.get("/manifest.json")
async def serve_manifest_root():
    return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/json")

@app.get("/sw.js")
async def serve_sw_root():
    return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})

@app.get("/icons/{filename}")
async def serve_icon_root(filename: str):
    f = FRONTEND_DIR / "icons" / filename
    if f.is_file():
        return FileResponse(f, media_type="image/png")

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
