"""
Auth via Supabase Auth (no bcrypt custom).
El trigger en DB crea el perfil en `usuarios` automáticamente.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from utils.logger import get_logger
from utils.supabase_client import get_client, get_service_client

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    mundo_analogias: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(body: RegisterRequest):
    db = get_service_client()
    logger.info(f"Registro: {body.email}")

    try:
        res = db.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True,          # confirmado directamente (sin email)
            "user_metadata": {"nombre": body.nombre},
        })
    except Exception as e:
        msg = str(e)
        if "already registered" in msg or "already exists" in msg:
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        raise HTTPException(status_code=400, detail=f"Error al registrar: {msg}")

    usuario_id = res.user.id

    # Actualizar mundo_analogias si viene
    if body.mundo_analogias:
        db.table("usuarios").update(
            {"mundo_analogias": body.mundo_analogias, "nombre": body.nombre}
        ).eq("id", usuario_id).execute()
    else:
        db.table("usuarios").update({"nombre": body.nombre}).eq("id", usuario_id).execute()

    # Login para devolver token
    login_res = get_client().auth.sign_in_with_password({
        "email": body.email,
        "password": body.password,
    })

    logger.info(f"Usuario registrado: {usuario_id}")
    return {
        "token": login_res.session.access_token,
        "usuario_id": usuario_id,
        "nombre": body.nombre,
        "email": body.email,
    }


@router.post("/login")
async def login(body: LoginRequest):
    logger.info(f"Login: {body.email}")
    try:
        res = get_client().auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    usuario_id = res.user.id

    # Datos del perfil
    perfil = get_service_client().table("usuarios").select("nombre, mundo_analogias").eq("id", usuario_id).execute()
    nombre = perfil.data[0]["nombre"] if perfil.data else res.user.email
    mundo_analogias = perfil.data[0].get("mundo_analogias") or "" if perfil.data else ""

    logger.info(f"Login exitoso: {usuario_id}")
    return {
        "token": res.session.access_token,
        "usuario_id": usuario_id,
        "nombre": nombre,
        "email": body.email,
        "mundo_analogias": mundo_analogias,
    }
