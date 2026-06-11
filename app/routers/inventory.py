import math
from datetime import date, timedelta
from typing import Any, Optional

import os
from dotenv import load_dotenv

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, case

from app.database import get_db
from app.models.inventory import SKU, InventoryRecord
from app.cache import (
    cache_get,
    cache_set,
    make_cache_key,
    TTL_SKU_LISTS,
    TTL_STOCK_DATA,
    TTL_ALERTS,
    TTL_SEARCH_RESULTS,
)

router = APIRouter()

load_dotenv()


@router.get("/skus")
async def get_skus(
    request: Request,  # needed so we can set request.state.cache_hit for middleware
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cache_key = make_cache_key("skus", category=category, skip=skip, limit=limit)

    cached = await cache_get(cache_key)
    if cached is not None:
        request.state.cache_hit = True  # signal to PerformanceMiddleware
        return cached
    request.state.cache_hit = False

    count_stmt = select(func.count()).select_from(SKU)
    if category:
        count_stmt = count_stmt.where(SKU.category == category)

    total: int = (await db.execute(count_stmt)).scalar() or 0

    stmt = select(SKU)
    if category:
        stmt = stmt.where(SKU.category == category)
    stmt = stmt.offset(skip).limit(limit)

    skus = (await db.execute(stmt)).scalars().all()

    result = {
        "total": total,
        "page": math.ceil(skip / limit) + 1 if limit else 1,
        "items": [
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "category": s.category,
                "unit": s.unit,
                "reorder_level": s.reorder_level,
                "shelf_life_days": s.shelf_life_days,
                "purchase_price": s.purchase_price,
                "selling_price": s.selling_price,
                "description": s.description,
            }
            for s in skus
        ],
    }

    await cache_set(cache_key, result, TTL_SKU_LISTS)
    return result


@router.get("/skus/{sku_id}")
async def get_sku(
    sku_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cache_key = make_cache_key("sku_detail", sku_id=sku_id)
    cached = await cache_get(cache_key)
    if cached is not None:
        request.state.cache_hit = True
        return cached
    request.state.cache_hit = False

    stmt = select(SKU).where(SKU.id == sku_id)
    sku = (await db.execute(stmt)).scalar_one_or_none()

    if not sku:
        raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")

    result = {
        "id": sku.id,
        "code": sku.code,
        "name": sku.name,
        "category": sku.category,
        "unit": sku.unit,
        "reorder_level": sku.reorder_level,
        "shelf_life_days": sku.shelf_life_days,
        "purchase_price": sku.purchase_price,
        "selling_price": sku.selling_price,
        "description": sku.description,
        "has_embedding": sku.embedding is not None,
    }

    await cache_set(cache_key, result, TTL_SKU_LISTS)
    return result


@router.get("/categories")
async def get_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cache_key = "categories:all"
    cached = await cache_get(cache_key)
    if cached is not None:
        request.state.cache_hit = True
        return cached
    request.state.cache_hit = False

    stmt = select(SKU.category).distinct().order_by(SKU.category)
    rows = (await db.execute(stmt)).all()

    result = {"categories": [r[0] for r in rows]}
    await cache_set(cache_key, result, TTL_SKU_LISTS)
    return result


@router.get("/stock")
async def get_stock(
    request: Request,
    sku_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cache_key = make_cache_key("stock", sku_id=sku_id)
    cached = await cache_get(cache_key)
    if cached is not None:
        request.state.cache_hit = True
        return cached
    request.state.cache_hit = False

    stmt = (
        select(
            SKU.id,
            SKU.code,
            SKU.name,
            SKU.category,
            SKU.unit,
            SKU.reorder_level,
            func.sum(InventoryRecord.quantity).label("total_quantity"),
        )
        .join(InventoryRecord, SKU.id == InventoryRecord.sku_id)
        .group_by(SKU.id, SKU.code, SKU.name, SKU.category, SKU.unit, SKU.reorder_level)
    )
    if sku_id:
        stmt = stmt.where(SKU.id == sku_id)

    rows = (await db.execute(stmt)).all()

    result = {
        "items": [
            {
                "sku_id": r.id,
                "code": r.code,
                "name": r.name,
                "category": r.category,
                "unit": r.unit,
                "reorder_level": r.reorder_level,
                "total_quantity": r.total_quantity,
                "needs_reorder": (r.total_quantity or 0) <= r.reorder_level,
            }
            for r in rows
        ]
    }

    await cache_set(cache_key, result, TTL_STOCK_DATA)
    return result


@router.get("/alerts")
async def get_alerts(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cache_key = "alerts:current"
    cached = await cache_get(cache_key)
    if cached is not None:
        request.state.cache_hit = True
        return cached
    request.state.cache_hit = False

    today = date.today()
    warn_date = today + timedelta(days=7)

    # Expiring soon
    expiring_stmt = (
        select(InventoryRecord, SKU)
        .join(SKU, InventoryRecord.sku_id == SKU.id)
        .where(InventoryRecord.expiry_date.isnot(None))
        .where(InventoryRecord.expiry_date >= today)
        .where(InventoryRecord.expiry_date <= warn_date)
        .where(InventoryRecord.quantity > 0)
        .order_by(InventoryRecord.expiry_date.asc())
    )
    expiring_rows = (await db.execute(expiring_stmt)).all()

    # Already expired
    expired_stmt = (
        select(InventoryRecord, SKU)
        .join(SKU, InventoryRecord.sku_id == SKU.id)
        .where(InventoryRecord.expiry_date.isnot(None))
        .where(InventoryRecord.expiry_date < today)
        .where(InventoryRecord.quantity > 0)
        .order_by(InventoryRecord.expiry_date.asc())
    )
    expired_rows = (await db.execute(expired_stmt)).all()

    # Low stock — sum quantity per SKU, compare to reorder level
    stock_subq = (
        select(
            InventoryRecord.sku_id,
            func.sum(InventoryRecord.quantity).label("total_qty"),
        )
        .group_by(InventoryRecord.sku_id)
        .subquery()
    )
    low_stock_stmt = (
        select(SKU, stock_subq.c.total_qty)
        .join(stock_subq, SKU.id == stock_subq.c.sku_id)
        .where(stock_subq.c.total_qty <= SKU.reorder_level)
        .order_by(stock_subq.c.total_qty.asc())
    )
    low_stock_rows = (await db.execute(low_stock_stmt)).all()

    result: dict[str, Any] = {
        "expiring_soon": [
            {
                "record_id": r.InventoryRecord.id,
                "sku_code": r.SKU.code,
                "sku_name": r.SKU.name,
                "category": r.SKU.category,
                "quantity": r.InventoryRecord.quantity,
                "expiry_date": r.InventoryRecord.expiry_date.isoformat(),
                "days_until_expiry": (r.InventoryRecord.expiry_date - today).days,
                "location": r.InventoryRecord.location,
            }
            for r in expiring_rows
        ],
        "expired": [
            {
                "record_id": r.InventoryRecord.id,
                "sku_code": r.SKU.code,
                "sku_name": r.SKU.name,
                "category": r.SKU.category,
                "quantity": r.InventoryRecord.quantity,
                "expiry_date": r.InventoryRecord.expiry_date.isoformat(),
                "days_overdue": (today - r.InventoryRecord.expiry_date).days,
                "location": r.InventoryRecord.location,
            }
            for r in expired_rows
        ],
        "low_stock": [
            {
                "sku_id": r.SKU.id,
                "sku_code": r.SKU.code,
                "sku_name": r.SKU.name,
                "category": r.SKU.category,
                "unit": r.SKU.unit,
                "total_quantity": r.total_qty,
                "reorder_level": r.SKU.reorder_level,
            }
            for r in low_stock_rows
        ],
        "summary": {
            "total_skus": (
                await db.execute(select(func.count()).select_from(SKU))
            ).scalar()
            or 0,
            "expiring_soon_count": len(expiring_rows),
            "expired_count": len(expired_rows),
            "low_stock_count": len(low_stock_rows),
        },
    }

    await cache_set(cache_key, result, TTL_ALERTS)
    return result


@router.get("/search")
async def semantic_search(
    request: Request,
    q: str = Query(..., min_length=2, description="Natural language search query"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Find SKUs by semantic similarity using pgvector cosine distance.

    How cosine similarity works in plain English:
    Imagine each SKU description is an arrow pointing in 1536-dimensional space.
    Arrows pointing in the same direction are semantically similar. Cosine similarity
    measures the angle between two arrows — 0° (angle=0) means identical meaning,
    90° (angle=1.0) means completely unrelated. We sort by smallest angle and
    return the top 10 closest matches.

    Example: searching "items that spoil quickly" finds dairy and frozen goods
    because their embeddings cluster near the concept of perishability — even
    though neither category name appears in the search query.

    Why async: generate_embedding() awaits an OpenAI API call; db.execute()
    awaits the pgvector cosine distance query on Postgres.

    Cache strategy: same query always returns the same results (given stable
    embeddings), so we cache for 120 seconds.
    """
    cache_key = make_cache_key("search", q=q.lower().strip())
    cached = await cache_get(cache_key)
    if cached is not None:
        request.state.cache_hit = True
        return cached
    request.state.cache_hit = False

    # Embed the search query using the same model that embedded the SKU descriptions.
    # await: HTTPS call to OpenAI text-embedding-3-small
    from app.services.embedding_service import generate_embedding

    try:
        query_embedding = await generate_embedding(q)
    except Exception as exc:
        if (
            str(os.getenv("IS_AI_ENABLED")) != "1"
            or str(os.getenv("IS_PRODUCTION")) == "1"
        ):
            raise HTTPException(
                status_code=404,
                detail="AI disabled. Please try again later",
            )
        else:
            raise HTTPException(
                status_code=503, detail=f"Embedding service unavailable: {exc}"
            )

    # pgvector cosine_distance() computes the angle-based distance between vectors.
    # Lower distance = more similar.
    # cosine_distance returns values in [0, 2]:
    #   0.0  = identical direction (100% similar)
    #   1.0  = orthogonal (unrelated)
    #   2.0  = opposite direction
    # We convert to similarity percentage: (1 - distance/2) * 100
    stmt = (
        select(
            SKU,
            SKU.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .where(SKU.embedding.isnot(None))
        .order_by(SKU.embedding.cosine_distance(query_embedding).asc())
        .limit(10)
    )

    try:
        rows = (await db.execute(stmt)).all()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Vector search failed — have you run the embedding job? ({exc})",
        )

    if not rows:
        if (
            str(os.getenv("IS_AI_ENABLED")) != "1"
            or str(os.getenv("IS_PRODUCTION")) == "1"
        ):
            raise HTTPException(
                status_code=404,
                detail="AI disabled. Please try again later",
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="No embeddings found. Run: python -m app.services.embedding_service",
            )

    result = {
        "query": q,
        "results": [
            {
                "id": r.SKU.id,
                "code": r.SKU.code,
                "name": r.SKU.name,
                "category": r.SKU.category,
                "unit": r.SKU.unit,
                "description": r.SKU.description,
                "similarity_score": round(float(1 - r.distance / 2) * 100, 1),
                # Distance for debugging — not shown in the UI
                "cosine_distance": round(float(r.distance), 4),
            }
            for r in rows
        ],
    }

    await cache_set(cache_key, result, TTL_SEARCH_RESULTS)
    return result


@router.get("/ask")
async def ask_vikram(
    q: str = Query(..., min_length=3, description="Plain English warehouse question"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Answer a plain-English warehouse question with a streamed GPT response.

    Returns a StreamingResponse — tokens arrive at the client as they are generated,
    creating a real-time "typing" effect in the frontend chat UI.

    Python note: StreamingResponse is FastAPI's built-in for returning chunked HTTP
    responses. The 'generator' parameter accepts any async iterable — including our
    async generator function from nlq_service.

    Why NOT cached: every response depends on real-time DB state AND is streamed —
    caching a stream is non-trivial and the latency difference is negligible vs the
    OpenAI API call time.

    Why async: StreamingResponse's generator must be an async generator (see
    nlq_service.ask_vikram_stream). The underlying calls await DB queries and
    OpenAI's streaming API.
    """

    if str(os.getenv("IS_AI_ENABLED")) != "1":
        raise HTTPException(
            status_code=404,
            detail="AI disabled. Please try again later",
        )

    from app.services.nlq_service import ask_vikram_stream

    # ask_vikram_stream is an async generator — it yields token strings as GPT produces them.
    # We wrap it in a plain 'generate' async generator to allow injecting a newline
    # at the end, ensuring the stream closes cleanly.
    async def generate():
        """Thin wrapper that forwards tokens from the NLQ service to the HTTP stream."""
        async for chunk in ask_vikram_stream(q, db):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            # Disable Nginx/proxy buffering so tokens reach the browser immediately
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
