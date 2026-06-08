"""
Alembic environment configuration.

This file is executed by Alembic when running 'alembic upgrade head' or
'alembic revision --autogenerate'. It connects to the database and runs
pending migrations.

Important: Alembic uses synchronous SQLAlchemy. We pull DATABASE_URL from the
environment and strip any async driver prefix (postgresql+asyncpg://) so Alembic
uses the standard psycopg2 driver, which it supports natively.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

load_dotenv()

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Override the database URL from environment ────────────────────────────────
# This ensures 'alembic upgrade head' uses the same database as the application,
# regardless of what is hardcoded in alembic.ini.
# Alembic doesn't support asyncpg — strip the async driver prefix if present.
_db_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
_sync_url = (
    _db_url
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("postgresql+psycopg2://", "postgresql://")
)
config.set_main_option("sqlalchemy.url", _sync_url)

# ── Import ALL models so Alembic knows about every table ─────────────────────
# 'autogenerate' compares Base.metadata to the live DB schema.
# If a model is not imported here, Alembic won't see it and won't generate
# migration scripts for it.
from app.models.inventory import SKU, InventoryRecord  # noqa: F401, E402
from app.models.metrics import APIMetric               # noqa: F401, E402
from app.database import Base                          # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (generate SQL scripts without a live connection).
    Used for generating SQL to review before applying, or for environments without
    direct DB access.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode with a live database connection.
    This is the normal mode used by 'alembic upgrade head'.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
