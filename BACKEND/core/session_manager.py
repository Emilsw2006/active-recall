"""
Gestiona el estado en memoria de las sesiones activas.

Prioridad de átomos: rojo → amarillo → nuevo → verde
Chunking: preguntas_por_sesion (máx 20)
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)

MAX_PREGUNTAS = 30  # límite duro global


@dataclass
class AtomoSesion:
    id: str
    titulo_corto: str
    texto_completo: str
    embedding: List[float]
    tema_id: str
    orden: int
    pregunta: Optional[str] = None
    uso_pista: bool = False  # True si el estudiante pidió pista → cap amarillo


@dataclass
class SesionActiva:
    sesion_id: str
    usuario_id: str
    usuario_mundo_analogias: str
    atomos: List[AtomoSesion]
    duration_type: str = "corta"
    indice_actual: int = 0
    estado: str = "IDLE"  # IDLE | SPEAKING_AI | LISTENING_USER | PROCESSING | WAITING_NEXT
    audio_buffer: bytes = field(default_factory=bytes)
    ultimo_audio_ts: Optional[datetime] = None
    tts_enabled: bool = True
    en_segundo_intento: bool = False
    kokoro_voice: str = "ef_dora"
    _created_at: datetime = field(default_factory=datetime.utcnow)
    _total_original: int = 0   # Total átomos antes de filtrar ya-respondidos
    _offset_inicial: int = 0   # Cuántos ya estaban respondidos al reanudar

    @property
    def atomo_actual(self) -> Optional[AtomoSesion]:
        if self.indice_actual < len(self.atomos):
            return self.atomos[self.indice_actual]
        return None

    @property
    def completada(self) -> bool:
        return self.indice_actual >= len(self.atomos)

    @property
    def progreso(self) -> dict:
        total = self._total_original if self._total_original > 0 else len(self.atomos)
        actual = self._offset_inicial + self.indice_actual + 1
        return {
            "actual": min(actual, total),
            "total": total,
        }


# Almacén en memoria de sesiones activas
_sesiones: Dict[str, SesionActiva] = {}


# ── Función principal: crear sesiones por asignatura ────────────────────────

async def crear_sesiones_asignatura(
    asignatura_id: str,
    usuario_id: str,
    preguntas_por_sesion: int = 10,
) -> List[List[dict]]:
    """
    Recopila todos los átomos de la asignatura, los prioriza
    (rojo → amarillo → nuevo → verde) y los divide en chunks
    de `preguntas_por_sesion` (máx 20).

    Devuelve una lista de chunks. Cada chunk es una lista de dicts
    de átomos listos para insertar como sesión en DB.
    """
    db = get_service_client()
    preguntas_por_sesion = min(max(preguntas_por_sesion, 1), MAX_PREGUNTAS)

    # 1. Temas de la asignatura (via documentos)
    docs_res = await asyncio.to_thread(
        lambda: db.table("documentos").select("id").eq("asignatura_id", asignatura_id).execute()
    )
    if not docs_res.data:
        logger.warning(f"Sin documentos para asignatura {asignatura_id}")
        return []

    doc_ids = [d["id"] for d in docs_res.data]
    temas_res = await asyncio.to_thread(
        lambda: db.table("temas").select("id").in_("documento_id", doc_ids).execute()
    )
    if not temas_res.data:
        return []

    tema_ids = [t["id"] for t in temas_res.data]

    # 2. Átomos sin duplicados
    atomos_res = await asyncio.to_thread(
        lambda: db.table("atomos").select("id, tema_id").in_("tema_id", tema_ids).is_("es_duplicado_de", "null").execute()
    )
    if not atomos_res.data:
        return []

    atomo_ids = [a["id"] for a in atomos_res.data]

    # 3. Historial: rojos y amarillos (prioridad alta)
    hist_res = await asyncio.to_thread(
        lambda: db.table("resultados").select("atomo_id, estado").in_("atomo_id", atomo_ids).execute()
    )
    ids_rojo = set()
    ids_amarillo = set()
    ids_verde = set()
    for r in (hist_res.data or []):
        estado = r["estado"]
        aid = r["atomo_id"]
        if estado == "rojo":
            ids_rojo.add(aid)
            ids_amarillo.discard(aid)
            ids_verde.discard(aid)
        elif estado == "amarillo" and aid not in ids_rojo:
            ids_amarillo.add(aid)
            ids_verde.discard(aid)
        elif estado == "verde" and aid not in ids_rojo and aid not in ids_amarillo:
            ids_verde.add(aid)

    def prioridad(aid: str) -> int:
        if aid in ids_rojo:    return 0
        if aid in ids_amarillo: return 1
        if aid not in ids_verde: return 2  # nuevo (sin historial)
        return 3                            # verde

    atomos_ordenados = sorted(atomo_ids, key=prioridad)

    # 4. Dividir en chunks
    chunks = []
    for i in range(0, len(atomos_ordenados), preguntas_por_sesion):
        chunk_ids = atomos_ordenados[i:i + preguntas_por_sesion]
        # Incluir tema_id para poder reconstruir la sesión
        chunk = [
            next(a for a in atomos_res.data if a["id"] == aid)
            for aid in chunk_ids
        ]
        chunks.append(chunk)

    logger.info(
        f"Asignatura {asignatura_id}: {len(atomo_ids)} átomos → "
        f"{len(chunks)} sesiones de {preguntas_por_sesion} preguntas"
    )
    return chunks


# ── Preparar átomos priorizados para temas elegidos ─────────────────────────

async def preparar_atomos_priorizados(
    temas_elegidos: List[str],
    usuario_id: str,
) -> List[dict]:
    """
    Recopila átomos de los temas elegidos, excluyendo duplicados,
    y los ordena por prioridad: rojo → amarillo → nuevo → verde.
    Devuelve lista de dicts con id, tema_id, orden, titulo_corto,
    texto_completo, embedding.
    """
    db = get_service_client()

    atomos_res = await asyncio.to_thread(
        lambda: db.table("atomos")
        .select("id, titulo_corto, texto_completo, embedding, tema_id, orden")
        .in_("tema_id", temas_elegidos)
        .is_("es_duplicado_de", "null")
        .execute()
    )
    if not atomos_res.data:
        return []

    atomo_ids = [a["id"] for a in atomos_res.data]

    # Historial de resultados para priorizar
    hist_res = await asyncio.to_thread(
        lambda: db.table("resultados")
        .select("atomo_id, estado")
        .in_("atomo_id", atomo_ids)
        .execute()
    )
    ids_rojo = set()
    ids_amarillo = set()
    ids_verde = set()
    for r in (hist_res.data or []):
        aid, estado = r["atomo_id"], r["estado"]
        if estado == "rojo":
            ids_rojo.add(aid); ids_amarillo.discard(aid); ids_verde.discard(aid)
        elif estado == "amarillo" and aid not in ids_rojo:
            ids_amarillo.add(aid); ids_verde.discard(aid)
        elif estado == "verde" and aid not in ids_rojo and aid not in ids_amarillo:
            ids_verde.add(aid)

    def prioridad(a):
        aid = a["id"]
        if aid in ids_rojo:     return (0, a["orden"])
        if aid in ids_amarillo: return (1, a["orden"])
        if aid not in ids_verde: return (2, a["orden"])  # nuevo
        return (3, a["orden"])                            # verde

    return sorted(atomos_res.data, key=prioridad)


def dividir_en_chunks(atomos: List[dict], preguntas_por_sesion: int) -> List[List[dict]]:
    """Divide una lista de átomos en chunks de tamaño preguntas_por_sesion."""
    preguntas_por_sesion = min(max(preguntas_por_sesion, 1), MAX_PREGUNTAS)
    chunks = []
    for i in range(0, len(atomos), preguntas_por_sesion):
        chunks.append(atomos[i:i + preguntas_por_sesion])
    return chunks


# ── Selección inteligente de átomos ─────────────────────────────────────────

def _seleccionar_por_temas(atomos: List[dict], limite: int) -> List[dict]:
    """
    Elige `limite` átomos distribuyendo entre temas en round-robin.
    Los átomos ya vienen ordenados por prioridad (rojo → nuevo → verde).
    Así se maximiza la cobertura de contenido en lugar de agotar el primer tema.
    """
    if len(atomos) <= limite:
        return atomos

    by_tema: dict = {}
    for a in atomos:
        by_tema.setdefault(a["tema_id"], []).append(a)

    temas = list(by_tema.values())
    result: List[dict] = []
    i = 0
    while len(result) < limite:
        progreso = False
        for tema_atoms in temas:
            if i < len(tema_atoms):
                result.append(tema_atoms[i])
                progreso = True
                if len(result) >= limite:
                    break
        if not progreso:
            break
        i += 1

    return result


# ── Carga de sesión en memoria ───────────────────────────────────────────────

async def cargar_sesion(
    sesion_id: str,
    usuario_id: str,
    temas_elegidos: List[str],
    duration_type: str = "corta",
    start_index: int = 0,
    max_atomos: Optional[int] = None,
) -> "SesionActiva":
    """
    Carga los átomos de los temas elegidos en memoria.
    Prioriza rojos, excluye ya respondidos en esta sesión.
    """
    db = get_service_client()
    inicio = datetime.now()
    from core.session_manager import MAX_PREGUNTAS

    logger.info(
        f"[{sesion_id}] Cargando sesión — tipo={duration_type} "
        f"start_index={start_index} temas={temas_elegidos}"
    )

    # Datos del usuario
    usuario_res = await asyncio.to_thread(
        lambda: db.table("usuarios").select("mundo_analogias").eq("id", usuario_id).execute()
    )
    mundo_analogias = ""
    if usuario_res.data:
        mundo_analogias = usuario_res.data[0].get("mundo_analogias") or ""

    # Átomos de los temas elegidos (sin duplicados)
    atomos_res = await asyncio.to_thread(
        lambda: db.table("atomos")
        .select("id, titulo_corto, texto_completo, embedding, tema_id, orden")
        .in_("tema_id", temas_elegidos)
        .is_("es_duplicado_de", "null")
        .execute()
    )

    if not atomos_res.data:
        logger.warning(f"[{sesion_id}] Sin átomos para los temas {temas_elegidos}")
        sesion = SesionActiva(
            sesion_id=sesion_id, usuario_id=usuario_id,
            usuario_mundo_analogias=mundo_analogias, atomos=[],
            duration_type=duration_type,
        )
        _sesiones[sesion_id] = sesion
        return sesion

    atomos_ids = [a["id"] for a in atomos_res.data]

    # Prioridad: rojos primero
    rojos_res = await asyncio.to_thread(
        lambda: db.table("resultados").select("atomo_id").eq("estado", "rojo").in_("atomo_id", atomos_ids).execute()
    )
    ids_rojos = {r["atomo_id"] for r in (rojos_res.data or [])}

    # Excluir ya respondidos en esta sesión
    ya_respondidos_res = await asyncio.to_thread(
        lambda: db.table("resultados").select("atomo_id").eq("sesion_id", sesion_id).execute()
    )
    ids_ya_respondidos = {r["atomo_id"] for r in (ya_respondidos_res.data or [])}
    if ids_ya_respondidos:
        logger.info(f"[{sesion_id}] Reanudando — saltando {len(ids_ya_respondidos)} ya respondidos")

    LARGA_MAX = 20  # cap hard para sesión larga

    def sort_key(a):
        return (0 if a["id"] in ids_rojos else 1, a["orden"])

    # Calcular límite según tipo, relativo al contenido disponible
    disponibles = [a for a in sorted(atomos_res.data, key=sort_key) if a["id"] not in ids_ya_respondidos]
    total_disp = len(disponibles)
    if max_atomos:
        limite = min(max_atomos, MAX_PREGUNTAS)
    elif duration_type == "repaso":
        limite = min(total_disp, MAX_PREGUNTAS)
    elif duration_type == "corta":
        limite = max(5, total_disp // 2)  # mitad del contenido elegido
    elif duration_type == "larga":
        limite = min(total_disp, LARGA_MAX)
    else:
        limite = min(total_disp, MAX_PREGUNTAS)  # plan, asignatura

    logger.info(f"[{sesion_id}] {total_disp} disponibles → límite={limite} ({duration_type})")

    # Para larga con más átomos de los que caben: distribuir entre temas (cobertura máxima)
    if duration_type == "larga" and total_disp > LARGA_MAX:
        atomos_ordenados = _seleccionar_por_temas(disponibles, LARGA_MAX)
    else:
        atomos_ordenados = disponibles[:limite]

    atomos = [
        AtomoSesion(
            id=a["id"],
            titulo_corto=a["titulo_corto"],
            texto_completo=a["texto_completo"],
            embedding=json.loads(a["embedding"]) if isinstance(a["embedding"], str) else (a["embedding"] or []),
            tema_id=a["tema_id"],
            orden=a["orden"],
        )
        for a in atomos_ordenados
    ]

    sesion = SesionActiva(
        sesion_id=sesion_id,
        usuario_id=usuario_id,
        usuario_mundo_analogias=mundo_analogias,
        atomos=atomos,
        duration_type=duration_type,
        indice_actual=0,
        _total_original=len(ids_ya_respondidos) + len(atomos),
        _offset_inicial=len(ids_ya_respondidos),
    )
    _sesiones[sesion_id] = sesion

    duracion = (datetime.now() - inicio).total_seconds()
    logger.info(
        f"[{sesion_id}] Sesión cargada en {duracion:.2f}s — "
        f"{len(atomos)} átomos ({len(ids_rojos)} rojos primero)"
    )
    return sesion


def get_sesion(sesion_id: str) -> Optional[SesionActiva]:
    return _sesiones.get(sesion_id)


def eliminar_sesion(sesion_id: str) -> None:
    _sesiones.pop(sesion_id, None)
    logger.info(f"[{sesion_id}] Sesión eliminada de memoria")


SESSION_TTL = timedelta(hours=2)


def cleanup_stale_sessions() -> int:
    """Elimina sesiones en memoria que superan el TTL. Devuelve cuántas eliminó."""
    now = datetime.utcnow()
    stale = [sid for sid, s in _sesiones.items() if now - s._created_at > SESSION_TTL]
    for sid in stale:
        _sesiones.pop(sid, None)
    if stale:
        logger.info(f"Cleanup: {len(stale)} sesiones stale eliminadas")
    return len(stale)


def active_session_count() -> int:
    return len(_sesiones)
