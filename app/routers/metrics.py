from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, text

from app.database import get_db
from app.models.metrics import APIMetric

router = APIRouter()


@router.get("")
async def get_metrics(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    # ── Per-endpoint aggregates ───────────────────────────────────────────────
    # percentile_cont(0.95) WITHIN GROUP (ORDER BY col) is PostgreSQL's
    # ordered-set aggregate for computing percentiles.
    # SQLAlchemy exposes it via func.percentile_cont(...).within_group(...).
    # P95 means: 95% of requests completed faster than this value.
    stats_stmt = (
        select(
            APIMetric.endpoint,
            APIMetric.method,
            func.count(APIMetric.id).label("request_count"),
            func.avg(APIMetric.response_time_ms).label("avg_ms"),
            func.min(APIMetric.response_time_ms).label("min_ms"),
            func.max(APIMetric.response_time_ms).label("max_ms"),
            # P95 latency: the response time threshold below which 95% of requests fall
            func.percentile_cont(0.95)
            .within_group(APIMetric.response_time_ms.asc())
            .label("p95_ms"),
            # Count cache hits using conditional SUM: 1 for True, 0 for False
            # Python note: case() in SQLAlchemy maps to SQL CASE WHEN...THEN...ELSE...END
            func.sum(
                case((APIMetric.cache_hit == True, 1), else_=0)  # noqa: E712
            ).label("cache_hits"),
        )
        .group_by(APIMetric.endpoint, APIMetric.method)
        .order_by(func.count(APIMetric.id).desc())
    )
    stats_result = await db.execute(stats_stmt)
    stats_rows = stats_result.all()

    # ── Slowest 10 requests today ─────────────────────────────────────────────
    # func.date() extracts the date portion from a timestamptz column.
    # Python note: date.today() returns a Python date object; SQLAlchemy knows
    # how to bind it as a SQL date literal.
    today = date.today()
    slowest_stmt = (
        select(APIMetric)
        .where(func.date(APIMetric.recorded_at) == today)
        .order_by(APIMetric.response_time_ms.desc())
        .limit(10)
    )
    slowest_result = await db.execute(slowest_stmt)
    slowest_rows = slowest_result.scalars().all()

    endpoint_stats = [
        {
            "endpoint": r.endpoint,
            "method": r.method,
            "request_count": r.request_count,
            "avg_response_time_ms": round(float(r.avg_ms or 0), 2),
            "min_response_time_ms": round(float(r.min_ms or 0), 2),
            "max_response_time_ms": round(float(r.max_ms or 0), 2),
            "p95_response_time_ms": round(float(r.p95_ms or 0), 2),
            # Cache hit rate as a percentage (0.0 – 100.0)
            "cache_hit_rate_pct": round(
                (
                    float(r.cache_hits or 0) / float(r.request_count) * 100
                    if r.request_count
                    else 0.0
                ),
                1,
            ),
            "cache_hits": int(r.cache_hits or 0),
        }
        for r in stats_rows
    ]

    slowest_requests = [
        {
            "endpoint": m.endpoint,
            "method": m.method,
            "response_time_ms": m.response_time_ms,
            "status_code": m.status_code,
            "cache_hit": m.cache_hit,
            "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
        }
        for m in slowest_rows
    ]

    return {
        "endpoints": endpoint_stats,
        "slowest_today": slowest_requests,
        "total_requests_tracked": sum(r["request_count"] for r in endpoint_stats),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
