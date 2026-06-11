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

# Fail loudly on startup if required env vars are missing.
_REQUIRED_ENV = ["DATABASE_URL", "OPENAI_API_KEY", "REDIS_URL"]
for _var in _REQUIRED_ENV:
    if not os.getenv(_var):
        raise RuntimeError(
            f"Required environment variable {_var!r} is not set.\n"
            f"Add it to your .env file and restart the server."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    yield
    # Graceful shutdown logic
    await close_redis()


# App instance
app = FastAPI(
    title="StockSense API",
    description="AI-Powered Warehouse Intelligence Platform — async, cached, semantic.",
    version="2.0.0",
    lifespan=lifespan,
)

# Performance middleware - outermost to include all other middlewares
app.add_middleware(PerformanceMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Response-Time-Ms", "X-Cache-Hit"],
)

# Routers
app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(metrics_router.router, prefix="/api/metrics", tags=["metrics"])


# Health check
@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """
    Liveness probe — used by Docker healthchecks and load balancers.
    Returns 200 as long as the process is alive and imports succeeded.
    """
    return {"status": "ok", "version": "2.0.0"}
