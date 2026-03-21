"""
Retry con backoff exponencial para llamadas a APIs externas.
"""

import asyncio
from typing import Callable, TypeVar

from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def with_retry(
    fn: Callable,
    max_retries: int = 2,
    backoff: float = 0.5,
    label: str = "API call",
) -> T:
    """
    Ejecuta `fn` (async o sync envuelta en to_thread) con reintentos.
    Backoff exponencial: 0.5s, 1.0s, ...
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = backoff * (attempt + 1)
                logger.warning(f"{label} intento {attempt + 1} falló: {e} — reintentando en {wait:.1f}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"{label} falló tras {max_retries + 1} intentos: {e}")
    raise last_error
