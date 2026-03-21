"""
Deduplicación cross-PDF por similitud coseno.

Compara átomos nuevos contra todos los existentes de la asignatura
(de documentos anteriores). Los embeddings ya están normalizados
(sentence-transformers normalize_embeddings=True), por lo que
similitud coseno = producto punto.

Umbral > 0.88 → duplicado automático (se marca es_duplicado_de).
"""

from typing import List

import numpy as np

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)

THRESHOLD_DUPLICADO = 0.88


async def deduplicar_atomos(
    documento_id: str,
    asignatura_id: str,
    atomos_nuevos: List[dict],  # [{id, texto_completo, embedding}, ...]
) -> dict:
    """
    Marca como duplicados los átomos del documento actual que ya
    existen en otro documento de la misma asignatura.

    Returns: {"duplicados": N, "nuevos": M}
    """
    db = get_service_client()

    # Átomos existentes de OTROS documentos (originales, no duplicados)
    existentes_res = (
        db.table("atomos")
        .select("id, embedding")
        .eq("asignatura_id", asignatura_id)
        .neq("documento_id", documento_id)
        .is_("es_duplicado_de", "null")
        .execute()
    )
    existentes = existentes_res.data or []

    if not existentes:
        logger.info(f"[{documento_id}] Sin átomos previos — sin deduplicación")
        return {"duplicados": 0, "nuevos": len(atomos_nuevos)}

    # Construir matriz de embeddings existentes (N_exist × 384)
    ids_exist = []
    vecs_exist = []
    for a in existentes:
        emb = a.get("embedding")
        if emb is None:
            continue
        if isinstance(emb, str):
            import json
            emb = json.loads(emb)
        ids_exist.append(a["id"])
        vecs_exist.append(emb)

    if not vecs_exist:
        return {"duplicados": 0, "nuevos": len(atomos_nuevos)}

    mat_exist = np.array(vecs_exist, dtype=np.float32)  # (N_exist, 384)

    duplicados = 0
    nuevos = 0

    for atomo in atomos_nuevos:
        emb_nuevo = atomo.get("embedding")
        if emb_nuevo is None:
            nuevos += 1
            continue

        vec_nuevo = np.array(emb_nuevo, dtype=np.float32)  # (384,)
        # Similitud coseno = dot product (embeddings ya normalizados)
        sims = mat_exist @ vec_nuevo  # (N_exist,)
        idx_max = int(np.argmax(sims))
        sim_max = float(sims[idx_max])

        if sim_max >= THRESHOLD_DUPLICADO:
            id_original = ids_exist[idx_max]
            db.table("atomos").update({
                "es_duplicado_de": id_original,
                "similitud_padre": round(sim_max, 4),
            }).eq("id", atomo["id"]).execute()
            duplicados += 1
            logger.info(
                f"[{documento_id}] Duplicado: {atomo['id'][:8]}... "
                f"→ {id_original[:8]}... (sim={sim_max:.3f})"
            )
        else:
            nuevos += 1

    logger.info(
        f"[{documento_id}] Deduplicación: {nuevos} nuevos, {duplicados} duplicados"
    )
    return {"duplicados": duplicados, "nuevos": nuevos}
