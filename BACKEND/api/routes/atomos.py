"""
GET /atomos?tema_id=XXX           → lista de átomos de un tema
GET /atomos/documento/{doc_id}    → lista de átomos de un documento
DELETE /atomos/{atomo_id}         → elimina un átomo
"""

import json
from fastapi import APIRouter, Query

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)
router = APIRouter(prefix="/atomos", tags=["atomos"])


@router.get("/documento/{documento_id}")
async def listar_atomos_por_documento(documento_id: str):
    """Lista los átomos de un documento (solo campos necesarios para UI)."""
    db = get_service_client()
    res = (
        db.table("atomos")
        .select("id, titulo_corto, orden")
        .eq("documento_id", documento_id)
        .order("orden")
        .execute()
    )
    atomos = res.data or []
    logger.info(f"Átomos documento {documento_id}: {len(atomos)} resultados")
    return [{"id": a["id"], "titulo": a.get("titulo_corto", "Concepto"), "orden": a.get("orden", 0)} for a in atomos]


@router.delete("/{atomo_id}")
async def eliminar_atomo(atomo_id: str):
    """Elimina un átomo por ID."""
    db = get_service_client()
    db.table("atomos").delete().eq("id", atomo_id).execute()
    logger.info(f"Átomo eliminado: {atomo_id}")
    return {"ok": True}


@router.get("/")
async def listar_atomos(tema_id: str = Query(..., description="UUID del tema")):
    db = get_service_client()

    res = (
        db.table("atomos")
        .select("id, titulo_corto, texto_completo, orden, embedding, subtema_id, tema_id")
        .eq("tema_id", tema_id)
        .order("orden")
        .execute()
    )

    atomos = res.data or []

    for a in atomos:
        emb = a.get("embedding")
        if emb is not None:
            if isinstance(emb, str):
                emb = json.loads(emb)
            a["tiene_embedding"] = True
            a["embedding_preview"] = {"dims": len(emb), "muestra": [round(x, 4) for x in emb[:3]]}
        else:
            a["tiene_embedding"] = False
            a["embedding_preview"] = None
        del a["embedding"]

    logger.info(f"Átomos tema {tema_id}: {len(atomos)} resultados")
    return atomos
