"""
performance.py - HTTP request performance monitoring middleware.

Role in system: Wraps every incoming HTTP request, measures wall-clock response time,
and persists the result to the api_metrics table. The data this writes is what the
/api/metrics endpoint reads to show P95 latency, cache hit rates, and slowest requests.

Python note: FastAPI middleware inherits from Starlette's BaseHTTPMiddleware.
C# equivalent is ASP.NET Core middleware registered in Program.cs with
app.Use(async (context, next) => { ... await next(); ... }). The pattern is identical:
intercept request → call next (downstream handlers) → process response.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.database import AsyncSessionLocal
from app.models.metrics import APIMetric

# Paths we deliberately exclude from metrics to keep the table clean.
# Logging /docs and /health every few seconds would flood the table.
_EXCLUDED_PATHS = frozenset(
    {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
        "/api/metrics",  # don't record requests to the metrics endpoint itself
    }
)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that records response time and cache status for every API request.

    Python note: __init__ must accept the ASGI 'app' argument and call super().__init__(app).
    In C# middleware the next delegate is injected via RequestDelegate — same concept.

    The dispatch() method is the equivalent of C# middleware's Invoke()/InvokeAsync().
    """

    def __init__(self, app: ASGIApp) -> None:
        """Pass the FastAPI app to Starlette's BaseHTTPMiddleware."""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process one HTTP request: time it, call the route, save metrics.

        Why async: call_next(request) dispatches through all remaining middleware
        and the actual route handler — this includes async DB calls, Redis lookups,
        and OpenAI calls. Awaiting it means our middleware never blocks the event
        loop while other requests are being served.

        Args:
            request: Starlette Request (method, path, headers, body, etc.)
            call_next: Calls the next middleware or route handler in the chain.

        Returns:
            The HTTP Response to send back to the client.
        """
        path = request.url.path

        # Skip non-API endpoints and excluded paths
        if path in _EXCLUDED_PATHS or not path.startswith("/api/"):
            return await call_next(request)  # await: full downstream dispatch

        # time.perf_counter() gives the highest-resolution timer available on the OS.
        # Python note: equivalent to C# Stopwatch.GetTimestamp() / Frequency.
        # Do NOT use time.time() here — it has ~15ms granularity on Windows.
        start = time.perf_counter()

        # await: dispatches request through all remaining middleware and the route.
        # After this line returns, request.state may contain cache_hit set by the route.
        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        # Routes that use caching set request.state.cache_hit = True before returning.
        # request.state is a simple namespace shared between middleware and routes
        # on the same request — it IS the same object, not a copy.
        cache_hit: bool = getattr(request.state, "cache_hit", False)

        # Persist the metric asynchronously.
        # We create a fresh session here — we can't use Depends(get_db) in middleware
        # because middleware runs outside FastAPI's dependency injection system.
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
                await session.commit()  # await: INSERT to Postgres
        except Exception:
            # Metrics failure must NEVER affect the main request.
            # If the api_metrics table doesn't exist yet, or the DB is down,
            # we still return the response normally.
            pass

        # Add timing header so developers can see it in browser DevTools
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

        return response
