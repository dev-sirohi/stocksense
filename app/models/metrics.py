from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


# One row per HTTP request. Written by PerformanceMiddleware.
class APIMetric(Base):
    __tablename__ = "api_metrics"

    id = Column(Integer, primary_key=True, index=True)

    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    cache_hit = Column(Boolean, nullable=False, default=False)
    recorded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<APIMetric {self.method} {self.endpoint} "
            f"{self.response_time_ms:.1f}ms cache={self.cache_hit}>"
        )
