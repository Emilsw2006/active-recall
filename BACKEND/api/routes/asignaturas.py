from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)
router = APIRouter(prefix="/asignaturas", tags=["asignaturas"])


class AsignaturaCreate(BaseModel):
    usuario_id: str        = Field(..., max_length=36)
    nombre: str            = Field(..., min_length=1, max_length=100)
    color: str | None      = Field(None, max_length=20)
    tipo: str | None       = Field(None, pattern="^(teorica|practica|mixta)$")


@router.get("/{usuario_id}")
async def listar_asignaturas(usuario_id: str):
    db = get_service_client()
    res = (
        db.table("asignaturas")
        .select("*")
        .eq("usuario_id", usuario_id)
        .order("fecha_creacion")
        .execute()
    )
    asignaturas = res.data or []

    # Enrich with document count
    for asig in asignaturas:
        try:
            docs_res = (
                db.table("documentos")
                .select("id", count="exact")
                .eq("asignatura_id", asig["id"])
                .execute()
            )
            asig["recuento_documentos"] = docs_res.count or 0
        except Exception:
            asig["recuento_documentos"] = 0

    return asignaturas


@router.post("/")
async def crear_asignatura(body: AsignaturaCreate):
    db = get_service_client()

    # Verificar usuario existe
    u = db.table("usuarios").select("id").eq("id", body.usuario_id).execute()
    if not u.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    row = {
        "usuario_id": body.usuario_id,
        "nombre": body.nombre,
        "color": body.color,
    }
    if body.tipo:
        row["tipo"] = body.tipo

    res = (
        db.table("asignaturas")
        .insert(row)
        .execute()
    )
    logger.info(f"Asignatura creada: {res.data[0]['id']} para usuario {body.usuario_id}")
    return res.data[0]


class AsignaturaUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=100)
    color: str | None  = Field(None, max_length=20)
    tipo: str | None   = Field(None, pattern="^(teorica|practica|mixta)$")


@router.put("/{asignatura_id}")
async def actualizar_asignatura(asignatura_id: str, body: AsignaturaUpdate):
    db = get_service_client()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    # When the user explicitly sets tipo, mark it as manual so the auto-detect
    # in practical_extractor stops overwriting it.
    if "tipo" in updates:
        updates["tipo_manual"] = True
    res = (
        db.table("asignaturas")
        .update(updates)
        .eq("id", asignatura_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")
    logger.info(f"Asignatura actualizada: {asignatura_id}")
    return res.data[0]


@router.delete("/{asignatura_id}")
async def eliminar_asignatura(asignatura_id: str):
    db = get_service_client()
    # Cascade: documentos → (temas/subtemas/atomos handled by DB FK or manual)
    db.table("asignaturas").delete().eq("id", asignatura_id).execute()
    logger.info(f"Asignatura eliminada: {asignatura_id}")
    return {"ok": True}
