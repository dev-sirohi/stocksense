"""
embedding_service.py - OpenAI text embeddings for semantic search.

Role in system: Converts SKU descriptions into numerical vectors (embeddings) that
capture their meaning. These vectors are stored in the SKU.embedding column
(pgvector Vector(1536)) and later used for cosine similarity search.

What are embeddings?
Think of each word and phrase as a point in 1536-dimensional space. Words with
similar meanings are placed near each other. "Dairy" and "milk" are close together;
"dairy" and "detergent" are far apart. This lets us search by MEANING, not by
exact keyword — searching "items that spoil quickly" finds dairy and frozen goods
even though neither category name appears in the query.

Why 1536 dimensions?
OpenAI's text-embedding-3-small model produces 1536-dimensional vectors. Each
dimension captures a different semantic aspect. 1536 is the model's native output
size — reducing it degrades quality. Storage cost: 1536 × 4 bytes = ~6 KB per SKU.
"""

from typing import Optional
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv
import os

from app.models.inventory import SKU

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set.\n"
        "Get your key from https://platform.openai.com/api-keys"
    )

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 100  # OpenAI supports up to 2048 texts per batch request

# Python note: a single module-level client instance is correct here.
# C# equivalent: a singleton HttpClient. Creating new clients per request
# wastes TCP connections and triggers rate-limit errors.
_openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_embedding(text: str) -> list[float]:
    """
    Generate a 1536-dimensional embedding vector for a single text string.

    Why async: openai_client.embeddings.create() makes an HTTPS request to
    OpenAI's API. Awaiting it yields control to the event loop so other
    coroutines can run while waiting for the response (typically 100–500 ms).

    Args:
        text: Text to embed, e.g. a SKU description.

    Returns:
        List of 1536 floats representing the text's semantic position.
    """
    # await: HTTPS call to api.openai.com
    response = await _openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    # response.data is a list — we sent one input, so index 0 is our result.
    # Python note: list indexing with [0] is the same as C# array[0].
    return response.data[0].embedding


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple texts in a single API call.

    One batch call is much faster than N individual calls because OpenAI
    processes the entire batch server-side in parallel. Use this whenever
    you need embeddings for more than a handful of texts.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors in the same order as the input texts.
    """
    if not texts:
        return []

    # await: single HTTPS call handles the entire batch
    response = await _openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    # OpenAI does not guarantee response order matches input order — sort by index.
    # Python note: sorted() with key= is like C# LINQ .OrderBy(x => x.Index).
    sorted_data = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in sorted_data]


async def embed_all_null_skus(db: AsyncSession) -> int:
    """
    Find every SKU with a null embedding and generate + store embeddings for them.

    Processes in batches of BATCH_SIZE to stay within OpenAI rate limits.
    Call this once after seeding the database.

    Why async: every batch calls OpenAI (async HTTP) and writes to Postgres
    (async I/O via AsyncSession). Both operations must be awaited.

    Args:
        db: AsyncSession from FastAPI's dependency injection or a script context.

    Returns:
        Number of SKUs that were successfully embedded.
    """
    # select() is the SQLAlchemy 2.0 API — required for AsyncSession.
    # The legacy db.query(SKU) only works with synchronous sessions.
    # Python note: select(SKU).where(...) is like C# LINQ .Where(s => s.Embedding == null)
    stmt = select(SKU).where(SKU.embedding.is_(None))
    result = await db.execute(stmt)  # await: executes the SELECT against Postgres
    skus = result.scalars().all()    # .scalars() unwraps Row tuples to plain SKU objects

    if not skus:
        print("All SKUs already have embeddings.")
        return 0

    total = len(skus)
    print(f"Generating embeddings for {total} SKUs in batches of {BATCH_SIZE}...")
    embedded_count = 0

    # range(start, stop, step) — like C# for (int i = 0; i < total; i += BATCH_SIZE)
    for i in range(0, total, BATCH_SIZE):
        batch = skus[i : i + BATCH_SIZE]

        # Use description if available; fall back to name for SKUs without description
        texts = [sku.description or sku.name for sku in batch]

        # await: single batch call to OpenAI for up to BATCH_SIZE texts
        embeddings = await generate_embeddings_batch(texts)

        # zip() pairs two iterables element-by-element — like C# Enumerable.Zip()
        for sku, embedding in zip(batch, embeddings):
            sku.embedding = embedding
            db.add(sku)  # marks the instance as dirty — SQLAlchemy will UPDATE it

        await db.commit()  # await: flush this batch to Postgres before moving on
        embedded_count += len(batch)
        print(f"  Progress: {embedded_count}/{total} SKUs embedded")

    print(f"Done. Embedded {embedded_count} SKUs.")
    return embedded_count


async def _run_embed_all() -> None:
    """Async entrypoint for the __main__ block below."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        count = await embed_all_null_skus(db)
        print(f"Embedding complete. {count} SKUs processed.")


async def embed_single_sku(sku_id: int, db: AsyncSession) -> Optional[list[float]]:
    """
    Embed a single SKU by ID and persist the embedding.

    Used for real-time embedding when a new SKU is created via the API.

    Returns:
        The embedding vector, or None if the SKU was not found.
    """
    stmt = select(SKU).where(SKU.id == sku_id)
    result = await db.execute(stmt)   # await: SELECT query
    sku = result.scalar_one_or_none() # None if no row found

    if sku is None:
        return None

    text = sku.description or sku.name
    embedding = await generate_embedding(text)  # await: HTTPS call to OpenAI

    sku.embedding = embedding
    db.add(sku)
    await db.commit()  # await: UPDATE to Postgres

    return embedding


if __name__ == "__main__":
    # Run with: python -m app.services.embedding_service
    import asyncio
    asyncio.run(_run_embed_all())
