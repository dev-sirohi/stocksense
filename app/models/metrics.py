"""
metrics.py - SQLAlchemy ORM model for the api_metrics table.

Role in system: The PerformanceMiddleware writes one row here per HTTP request,
recording endpoint, method, status code, response time, and whether it was a
cache hit. The /api/metrics endpoint aggregates these rows to compute P95,
averages, and cache effectiveness — the "money shot" for the portfolio.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


class APIMetric(Base):
    """One row per HTTP request. Written by PerformanceMiddleware."""

    __tablename__ = "api_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Which endpoint was hit, e.g. '/api/inventory/skus'
    endpoint = Column(String(255), nullable=False, index=True)

    # HTTP verb: GET, POST, etc.
    method = Column(String(10), nullable=False)

    # HTTP response status code: 200, 404, 500, etc.
    status_code = Column(Integer, nullable=False)

    # Wall-clock response time measured by the middleware, in milliseconds.
    # Float so we can represent sub-millisecond precision (e.g. 0.87 ms from cache).
    response_time_ms = Column(Float, nullable=False)

    # True when the response was served from Redis without hitting Postgres.
    # This is the key column for demonstrating caching impact in the Metrics page.
    cache_hit = Column(Boolean, nullable=False, default=False)

    # Postgres fills this automatically using server time (not Python time).
    # index=True so the "slowest requests today" query can use it efficiently.
    recorded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        """String representation for logging/debugging."""
        return (
            f"<APIMetric {self.method} {self.endpoint} "
            f"{self.response_time_ms:.1f}ms cache={self.cache_hit}>"
        )
