"""
main.py - FastAPI application factory and startup/shutdown lifecycle.

Role in system: Entry point for the ASGI server (Uvicorn). Registers all routers,
middleware, and lifecycle hooks. Uvicorn imports the 'app' object from this module.

Python note: In ASP.NET Core you'd have Program.cs with WebApplication.CreateBuilder().
FastAPI's equivalent is instantiating FastAPI() and configuring it directly in code —
no service locator, no configuration XML, just Python functions.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import inventory
from app.routers import metrics as metrics_router
from app.middleware.performance import PerformanceMiddleware
from app.cache import close_redis

load_dotenv()

# ── Startup validation ────────────────────────────────────────────────────────
# Fail loudly on startup if required env vars are missing. It is far better to
# crash with a clear error message than to serve requests that silently fail later.
_REQUIRED_ENV = ["DATABASE_URL", "OPENAI_API_KEY", "REDIS_URL"]
for _var in _REQUIRED_ENV:
    if not os.getenv(_var):
        raise RuntimeError(
            f"Required environment variable {_var!r} is not set.\n"
            f"Add it to your .env file and restart the server."
        )


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown.

    Python note: @asynccontextmanager transforms an async generator into a context
    manager. FastAPI runs the code before 'yield' on startup and after 'yield' on
    shutdown. C# equivalent: IHostedService.StartAsync / StopAsync.

    Why async: closing the Redis connection pool requires awaiting aclose().
    """
    # Startup: modules initialise lazily — nothing to do explicitly here.
    yield
    # Shutdown: close the shared Redis connection pool gracefully.
    # Without this, uvicorn would terminate the connections abruptly.
    await close_redis()


# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="StockSense API",
    description="AI-Powered Warehouse Intelligence Platform — async, cached, semantic.",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
# Python note: Starlette processes middleware in the REVERSE order of registration.
# The LAST middleware added wraps OUTERMOST (runs first on request, last on response).
# We want PerformanceMiddleware outermost so it times the entire request chain
# including CORS header injection.
app.add_middleware(PerformanceMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Response-Time-Ms", "X-Cache-Hit"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(metrics_router.router, prefix="/api/metrics", tags=["metrics"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """
    Liveness probe — used by Docker healthchecks and load balancers.
    Returns 200 as long as the process is alive and imports succeeded.
    """
    return {"status": "ok", "version": "2.0.0"}
