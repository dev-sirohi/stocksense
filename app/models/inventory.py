from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import (
    func,
)  # Allows calling SQL functions without writing SQL strings

from pgvector.sqlalchemy import Vector  # type: ignore

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
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inventory_records = relationship("InventoryRecords", back_populates="sku")

    def __repr__(self):
        return f"SKU {self.code} - {self.name}"


class InventoryRecord(Base):
    __tablename__ = "inventory_records"

    id = Column(Integer, primary_key=True, index=True)
    sku_id = Column(
        Integer, ForeignKey("skus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity = Column(Integer, nullable=False, default=0)
    received_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    location = Column(String(255), nullable=True)
    batch_number = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sku = relationship("SKU", back_populates="inventory_records")

    def __repr__(self):
        return f"<InventoryRecord SKU:{self.sku_id} Qty:{self.quantity} Expires:{self.expiry_date}>"
