from fastapi import APIRouter, HTTPException

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)
router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.get("/{usuario_id}")
async def listar_flashcards(usuario_id: str):
    db = get_service_client()

    res = (
        db.table("flashcards")
        .select(
            "*, atomos(titulo_corto, texto_completo)"
        )
        .eq("usuario_id", usuario_id)
        .order("veces_fallada", desc=True)
        .execute()
    )

    return res.data or []
