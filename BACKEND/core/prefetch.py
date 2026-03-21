"""
Prefetch rolling: genera la siguiente pregunta + TTS mientras el usuario responde.
Buffer de máximo 2 preguntas pre-generadas.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Awaitable, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PrefetchedQuestion:
    atomo_index: int
    pregunta_texto: str
    audio_base64: str
    audio_format: str
    generated_at: datetime


class PrefetchManager:
    """
    Gestiona un buffer de preguntas pre-generadas para una sesión.
    Genera en background mientras el usuario responde la pregunta actual.
    """

    def __init__(
        self,
        sesion,  # SesionActiva
        generar_pregunta_fn: Callable,
        tts_fn: Callable[..., Awaitable[Tuple[str, str]]],
    ):
        self._sesion = sesion
        self._generar_pregunta = generar_pregunta_fn
        self._tts_fn = tts_fn
        self._buffer: dict[int, PrefetchedQuestion] = {}  # index → prefetched
        self._tasks: dict[int, asyncio.Task] = {}
        self._stopped = False

    async def prefetch_next(self, index: int) -> None:
        """Lanza prefetch para el índice dado (si no está ya en buffer/generando)."""
        if self._stopped:
            return
        if index >= len(self._sesion.atomos):
            return  # No hay más átomos
        if index in self._buffer:
            return  # Ya está listo
        if index in self._tasks and not self._tasks[index].done():
            return  # Ya se está generando

        self._tasks[index] = asyncio.create_task(self._generate(index))

    async def _generate(self, index: int) -> None:
        """Genera pregunta + TTS para un átomo."""
        if self._stopped or index >= len(self._sesion.atomos):
            return

        atomo = self._sesion.atomos[index]
        try:
            # Generar pregunta (con cache por atomo_id)
            pregunta = await self._generar_pregunta(
                atomo.id, atomo.texto_completo, atomo.titulo_corto
            )
            atomo.pregunta = pregunta  # Cache en el átomo

            # Generar TTS solo si está habilitado
            audio_b64, audio_fmt = "", "mp3"
            if self._sesion.tts_enabled:
                audio_b64, audio_fmt = await self._tts_fn(pregunta)

            if not self._stopped:
                self._buffer[index] = PrefetchedQuestion(
                    atomo_index=index,
                    pregunta_texto=pregunta,
                    audio_base64=audio_b64,
                    audio_format=audio_fmt,
                    generated_at=datetime.utcnow(),
                )
                logger.info(f"[{self._sesion.sesion_id}] Prefetch listo para índice {index}")

                # Prefetch siguiente también (máx 2 en buffer)
                if len(self._buffer) < 2:
                    await self.prefetch_next(index + 1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[{self._sesion.sesion_id}] Prefetch falló para índice {index}: {e}")

    def get_if_ready(self, index: int) -> Optional[PrefetchedQuestion]:
        """Devuelve la pregunta prefetched si está lista, None si no."""
        return self._buffer.pop(index, None)

    def invalidate(self) -> None:
        """Invalida todo el buffer (ej: cambio de modo TTS)."""
        self._buffer.clear()
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()
        logger.info(f"[{self._sesion.sesion_id}] Prefetch buffer invalidado")

    async def stop(self) -> None:
        """Cancela todo y limpia."""
        self._stopped = True
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._buffer.clear()
