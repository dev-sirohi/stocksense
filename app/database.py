"""
database.py - Async SQLAlchemy engine, session factory, and FastAPI dependency.

Role in system: All database access flows through this module. Route handlers receive
an AsyncSession via FastAPI's Depends(get_db) — they never create sessions directly.
This is the single source of truth for DB configuration.

Python note: In C# you'd register DbContext in Startup.cs with AddDbContext<T>() and
receive it via constructor injection. In Python/FastAPI, dependencies are plain
functions or generators passed to Depends() — no DI container, no registration step.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

# ── Environment validation ──────────────────────────────────────────────────
# Validate at import time so misconfiguration surfaces immediately on startup,
# not buried in the first database call during a live request.
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set.\n"
        "Expected format: postgresql://user:pass@host:5432/dbname\n"
        "Add it to your .env file."
    )

# ── URL normalisation ───────────────────────────────────────────────────────
# asyncpg (the async Postgres driver) requires the 'postgresql+asyncpg://' scheme.
# Alembic and seed scripts need the plain sync 'postgresql://' scheme.
# We derive both from the single DATABASE_URL in .env so you only update one place.

# Python note: str.replace(old, new, count) replaces the first 'count' occurrences.
# The count=1 prevents accidentally replacing a second occurrence deeper in the URL.
if "postgresql+asyncpg://" in DATABASE_URL:
    ASYNC_DATABASE_URL = DATABASE_URL
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
elif "postgresql+psycopg2://" in DATABASE_URL:
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://", 1)
else:
    # Bare postgresql:// — assume psycopg2-style, add asyncpg prefix for the app
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    SYNC_DATABASE_URL = DATABASE_URL  # already sync-compatible

# ── Async engine ────────────────────────────────────────────────────────────
# create_async_engine is the async counterpart to SQLAlchemy's create_engine.
# The engine manages a connection pool — connections are reused across requests.
#
# pool_pre_ping=True: before handing out a pooled connection, test it with a
# lightweight "SELECT 1". This prevents "connection closed" errors after the DB
# restarts or drops idle connections.
#
# pool_size + max_overflow: up to 10 persistent connections, 20 overflow allowed
# under burst traffic, then requests queue until a slot opens.
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,          # set True during development to log generated SQL
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ─────────────────────────────────────────────────────────
# async_sessionmaker is the async equivalent of sessionmaker.
#
# expire_on_commit=False is critical for async code. Normally SQLAlchemy expires
# all ORM attributes after a commit so they reload from DB on next access. In async,
# that lazy reload requires an await — but Python properties cannot be async.
# Setting False keeps attributes valid post-commit without an extra DB round-trip.
#
# Python note: C# equivalent is registering DbContext with Scoped lifetime — each
# request gets its own instance, and it is disposed (closed) after the request ends.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── ORM base ─────────────────────────────────────────────────────────────────
# All ORM model classes inherit from Base. SQLAlchemy registers them in
# Base.metadata, which Alembic reads to auto-generate migration scripts.
#
# Python note: declarative_base() returns a class (not an instance). Your models
# inherit from this class. C# equivalent: DbContext.Set<T>() registration.
Base = declarative_base()


async def get_db():
    """
    FastAPI dependency that yields a database session and guarantees cleanup.

    Usage in route:
        db: AsyncSession = Depends(get_db)

    Python note: 'async def' combined with 'yield' creates an async generator
    function — C# equivalent is IAsyncEnumerable<T> with yield return.
    FastAPI calls next() before the route runs (entering the try block and yielding
    the session), then resumes after the yield for cleanup — similar to C# using().

    Why async: SQLAlchemy's AsyncSession methods (execute, commit, rollback) all
    make network calls to Postgres. We must await them to avoid blocking the event
    loop, which would stall every other concurrent request.
    """
    # 'async with' is the async form of C# 'using' — calls __aenter__ on entry
    # and __aexit__ on exit (even if an exception is raised).
    async with AsyncSessionLocal() as session:
        try:
            yield session          # hand the session to the route function
            await session.commit() # await: flush pending writes to Postgres
        except Exception:
            await session.rollback()  # await: undo any partial writes
            raise                  # re-raise so FastAPI returns a 500 response
