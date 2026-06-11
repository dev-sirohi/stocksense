import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.database import AsyncSessionLocal
from app.models.metrics import APIMetric

# Ignore these endpoints to keep data clean
_EXCLUDED_PATHS = frozenset(
    {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
        "/api/metrics",
    }
)


class PerformanceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path in _EXCLUDED_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # time.perf_counter() gives the highest-resolution timer available on the OS.
        # Do NOT use time.time() here — it has ~15ms granularity on Windows.
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        cache_hit: bool = getattr(request.state, "cache_hit", False)

        # We can't use Depends(get_db) in middleware because middleware runs outside FastAPI's dependency injection system.
        try:
            async with AsyncSessionLocal() as session:
                metric = APIMetric(
                    endpoint=path,
                    method=request.method,
                    status_code=response.status_code,
                    response_time_ms=round(elapsed_ms, 3),
                    cache_hit=cache_hit,
                )
                session.add(metric)
                await session.commit()
        except Exception:
            pass

        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

        return response
