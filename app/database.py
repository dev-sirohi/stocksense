from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

# Env vars check
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set.\n"
        "Expected format: postgresql://user:pass@host:5432/dbname\n"
        "Add it to your .env file."
    )

# Assume postgresql as base db url
# Normalize the urls for both synchronous and asynchronous dependencies
if "postgresql+asyncpg://" in DATABASE_URL:
    ASYNC_DATABASE_URL = DATABASE_URL
    SYNC_DATABASE_URL = DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
elif "postgresql+psycopg2://" in DATABASE_URL:
    ASYNC_DATABASE_URL = DATABASE_URL.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://", 1
    )
    SYNC_DATABASE_URL = DATABASE_URL.replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )
else:
    ASYNC_DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    SYNC_DATABASE_URL = DATABASE_URL

# Create engine
__engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=str(os.getenv("IS_PRODUCTION")) != "1",  # False for production
    pool_pre_ping=True,  # Pings with SELECT 1 before handing out a pool connection
    pool_size=10,
    max_overflow=20,
)

# Create local session with engine and config
__asyncSessionLocal = async_sessionmaker(
    bind=__engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,  # flush puts the data into the db but commits persists it. flush is always called during commit.
)


# Provide a function to get a session when needed - Usually used for dependency injection
async def get_db():
    # 'async with' uses __aenter__ instead of __enter__
    # likewise it uses __aexit__ instead of __exit__
    async with __asyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ORM Base - Models inherit this
Base = declarative_base()
AsyncSessionLocal = __asyncSessionLocal
