"""
Vectoriza átomos con sentence-transformers (all-MiniLM-L6-v2, 384 dims).
Guarda embeddings en Supabase.

IMPORTANTE: model.encode() es CPU-bound y síncrono. Se ejecuta en un
thread pool via run_in_executor para no bloquear el event loop de uvicorn
durante la vectorización (que puede durar 15-30s con 50+ átomos).
"""

import asyncio
from datetime import datetime
from functools import partial
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Cargando modelo sentence-transformers all-MiniLM-L6-v2...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Modelo cargado correctamente")
    return _model


def _encode_sync(textos: List[str]) -> np.ndarray:
    """Codificación síncrona — se llama desde run_in_executor, no bloquea el event loop."""
    model = get_model()
    return model.encode(textos, normalize_embeddings=True, show_progress_bar=False)


def embed_texto(texto: str) -> List[float]:
    """Genera embedding para un texto. Devuelve lista de 384 floats."""
    model = get_model()
    vector = model.encode(texto, normalize_embeddings=True)
    return vector.tolist()


async def vectorize_atomos(
    atomos: List[dict],
    documento_id: str,
) -> None:
    """
    Vectoriza una lista de átomos y guarda los embeddings en Supabase.
    Cada átomo debe tener 'id' y 'texto_completo'.

    La codificación corre en un thread pool para no bloquear el event loop.
    """
    if not atomos:
        logger.warning(f"[{documento_id}] No hay átomos para vectorizar")
        return

    db = get_service_client()
    inicio = datetime.now()
    logger.info(f"[{documento_id}] Vectorizando {len(atomos)} átomos (thread pool)...")

    textos = [a["texto_completo"] for a in atomos]

    # ── Clave: corre en thread pool — el event loop queda libre ──────────────
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(None, _encode_sync, textos)
    # ─────────────────────────────────────────────────────────────────────────

    errores = 0
    for atomo, embedding in zip(atomos, embeddings):
        try:
            vec = embedding.tolist()
            db.table("atomos").update({"embedding": vec}).eq("id", atomo["id"]).execute()
            atomo["embedding"] = vec  # disponible para deduplicación post-vectorización
        except Exception as e:
            logger.error(
                f"[{documento_id}] Error guardando embedding del átomo {atomo['id']}: {e}"
            )
            errores += 1

    duracion = (datetime.now() - inicio).total_seconds()
    logger.info(
        f"[{documento_id}] Vectorización completada en {duracion:.1f}s "
        f"({len(atomos) - errores}/{len(atomos)} exitosos)"
    )
