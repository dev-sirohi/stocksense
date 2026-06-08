from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import date, timedelta
from typing import Optional
import math

from app.database import get_db
from app.models.inventory import SKU, InventoryRecord

router = APIRouter()


@router.get("/skus")
def get_skus(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(SKU)

    if category:
        query = query.filter(SKU.category == category)

    total = query.count()

    skus = query.offset(skip).limit(limit).all()

    return {
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


@router.get("/skus/{sku_id}")
def get_sku(sku_id: int, db: Session = Depends(get_db)):
    """Get a single SKU by ID."""

    sku = db.query(SKU).filter(SKU.id == sku_id).first()

    if not sku:
        raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")

    return sku


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(SKU.category).distinct().all()
    return {"categories": [c[0] for c in categories]}


@router.get("/stock")
def get_stock(sku_id: Optional[int] = None, db: Session = Depends(get_db)):

    query = (
        db.query(
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
        query = query.filter(SKU.id == sku_id)

    results = query.all()

    return {
        "items": [
            {
                "sku_id": r.id,
                "code": r.code,
                "name": r.name,
                "category": r.category,
                "unit": r.unit,
                "reorder_level": r.reorder_level,
                "total_quantity": r.total_quantity,
                "needs_reorder": r.total_quantity <= r.reorder_level,
            }
            for r in results
        ]
    }


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    today = date.today()
    expiry_warning_date = today + timedelta(days=7)

    # ── Expiring soon ──
    expiring_soon = (
        db.query(InventoryRecord, SKU)
        .join(SKU, InventoryRecord.sku_id == SKU.id)
        .filter(InventoryRecord.expiry_date != None)
        .filter(InventoryRecord.expiry_date >= today)
        .filter(InventoryRecord.expiry_date <= expiry_warning_date)
        .filter(InventoryRecord.quantity > 0)
        .all()
    )

    # ── Already expired ──
    expired = (
        db.query(InventoryRecord, SKU)
        .join(SKU, InventoryRecord.sku_id == SKU.id)
        .filter(InventoryRecord.expiry_date != None)
        .filter(InventoryRecord.expiry_date < today)
        .filter(InventoryRecord.quantity > 0)
        .all()
    )

    # ── Low stock ──
    # Subquery: total quantity per SKU
    stock_subquery = (
        db.query(
            InventoryRecord.sku_id,
            func.sum(InventoryRecord.quantity).label("total_qty"),
        )
        .group_by(InventoryRecord.sku_id)
        .subquery()
    )

    low_stock = (
        db.query(SKU, stock_subquery.c.total_qty)
        .join(stock_subquery, SKU.id == stock_subquery.c.sku_id)
        .filter(stock_subquery.c.total_qty <= SKU.reorder_level)
        .all()
    )

    return {
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
            for r in expiring_soon
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
            for r in expired
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
            for r in low_stock
        ],
        "summary": {
            "expiring_soon_count": len(expiring_soon),
            "expired_count": len(expired),
            "low_stock_count": len(low_stock),
        },
    }
