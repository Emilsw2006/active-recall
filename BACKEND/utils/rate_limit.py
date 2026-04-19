"""
Simple in-memory rate limiter middleware.
No extra dependencies — uses only stdlib + Starlette.

Tiers (per IP, per 60-second window):
  AUTH   /auth/login, /auth/register        → 15 req/min  (brute-force protection)
  UPLOAD /documento/upload                  → 20 req/min
  WS     /ws                                → 10 req/min  (WebSocket handshake)
  GLOBAL everything else                    → 200 req/min
"""

from collections import defaultdict
from time import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    _AUTH_PATHS   = {"/auth/login", "/auth/register"}
    _UPLOAD_PATHS = {"/documento/upload"}
    _WS_PATHS     = {"/ws"}

    _TIERS = {
        "auth":   15,
        "upload": 20,
        "ws":     10,
        "global": 200,
    }

    def __init__(self, app):
        super().__init__(app)
        self._data: dict = defaultdict(list)

    def _allow(self, bucket: str, limit: int, window: int = 60) -> bool:
        now = time()
        hits = self._data[bucket]
        # Prune expired
        self._data[bucket] = [t for t in hits if now - t < window]
        if len(self._data[bucket]) >= limit:
            return False
        self._data[bucket].append(now)
        return True

    async def dispatch(self, request, call_next):
        ip   = request.client.host if request.client else "anon"
        path = request.url.path

        if path in self._AUTH_PATHS:
            ok = self._allow(f"auth:{ip}", self._TIERS["auth"])
            msg = "Demasiados intentos. Espera un minuto."
        elif path in self._UPLOAD_PATHS:
            ok = self._allow(f"upload:{ip}", self._TIERS["upload"])
            msg = "Límite de subidas alcanzado. Espera un momento."
        elif path in self._WS_PATHS:
            ok = self._allow(f"ws:{ip}", self._TIERS["ws"])
            msg = "Demasiadas conexiones. Espera un momento."
        else:
            ok = self._allow(f"global:{ip}", self._TIERS["global"])
            msg = "Demasiadas peticiones. Espera un momento."

        if not ok:
            return JSONResponse({"detail": msg}, status_code=429)

        return await call_next(request)
