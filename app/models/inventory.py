from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func  # func lets us call SQL functions like now() or sum()

from pgvector.sqlalchemy import Vector

from app.database import Base


class SKU(Base):
    __tablename__ = "skus"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(255), nullable=False, index=True)
    unit = Column(String(20), nullable=False)
    reorder_level = Column(Integer, nullable=False, default=10)
    shelf_life_days = Column(Integer, nullable=True)
    purchase_price = Column(Float, nullable=False, default=0.0)
    selling_price = Column(Float, nullable=False, default=0.0)
    description = Column(Text, nullable=True)

    # pgvector column — stores a 1536-float vector alongside normal columns.
    # NULL until embed_all_null_skus() runs after seeding.
    embedding = Column(Vector(1536), nullable=True)

    # server_default means Postgres fills this column on INSERT using its own clock,
    # not Python's time. More reliable when multiple app instances run in parallel.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # One-to-many relationship: one SKU → many InventoryRecords.
    # The string "InventoryRecord" must match the exact class name defined below.
    # Python note: SQLAlchemy uses the string name to avoid circular imports —
    # models can reference each other without importing each other directly.
    inventory_records = relationship("InventoryRecord", back_populates="sku")

    def __repr__(self) -> str:
        return f"<SKU {self.code} - {self.name}>"


class InventoryRecord(Base):
    __tablename__ = "inventory_records"

    id = Column(Integer, primary_key=True, index=True)

    sku_id = Column(
        Integer, ForeignKey("skus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity = Column(Integer, nullable=False, default=0)
    received_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)  # None for non-perishable items
    location = Column(String(255), nullable=True)
    batch_number = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # back_populates="inventory_records" must match the attribute name on SKU.
    sku = relationship("SKU", back_populates="inventory_records")

    def __repr__(self) -> str:
        return (
            f"<InventoryRecord SKU:{self.sku_id} "
            f"Qty:{self.quantity} Expires:{self.expiry_date}>"
        )
