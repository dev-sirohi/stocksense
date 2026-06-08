"""add api_metrics table

Revision ID: a1b2c3d4e5f6
Revises: 296eba3522e7
Create Date: 2026-06-09 10:00:00.000000

Creates the api_metrics table used by PerformanceMiddleware to record
response times, cache hits, and HTTP status codes for every API request.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "296eba3522e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the api_metrics table."""
    op.create_table(
        "api_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Float(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_metrics_id"), "api_metrics", ["id"], unique=False)
    op.create_index(op.f("ix_api_metrics_endpoint"), "api_metrics", ["endpoint"], unique=False)
    op.create_index(op.f("ix_api_metrics_recorded_at"), "api_metrics", ["recorded_at"], unique=False)


def downgrade() -> None:
    """Drop the api_metrics table."""
    op.drop_index(op.f("ix_api_metrics_recorded_at"), table_name="api_metrics")
    op.drop_index(op.f("ix_api_metrics_endpoint"), table_name="api_metrics")
    op.drop_index(op.f("ix_api_metrics_id"), table_name="api_metrics")
    op.drop_table("api_metrics")
