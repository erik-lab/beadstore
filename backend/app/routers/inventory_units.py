import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.enums import InventoryUnitStatus, UnitType
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.schemas.inventory_unit import (
    InventoryAdjustmentCreate,
    InventoryUnitCreate,
    InventoryUnitRead,
    InventoryUnitUpdate,
)

router = APIRouter(prefix="/inventory-units", tags=["inventory-units"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[InventoryUnitRead])
def list_inventory_units(
    db: Session = Depends(get_db),
    search: str | None = None,
    product_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID | None = None,
    status_filter: InventoryUnitStatus | None = Query(default=None, alias="status"),
    unit_type: UnitType | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    query = db.query(InventoryUnit)
    if search:
        pattern = f"%{search}%"
        query = query.outerjoin(Product, InventoryUnit.product_id == Product.id).filter(
            or_(
                InventoryUnit.unresolved_description.ilike(pattern),
                InventoryUnit.notes.ilike(pattern),
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
            )
        )
    if product_id:
        query = query.filter(InventoryUnit.product_id == product_id)
    if location_id:
        query = query.filter(InventoryUnit.location_id == location_id)
    if vendor_id:
        query = query.filter(InventoryUnit.vendor_id == vendor_id)
    if status_filter:
        query = query.filter(InventoryUnit.status == status_filter)
    if unit_type:
        query = query.filter(InventoryUnit.unit_type == unit_type)
    return query.order_by(InventoryUnit.received_date.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=InventoryUnitRead, status_code=status.HTTP_201_CREATED)
def create_inventory_unit(payload: InventoryUnitCreate, db: Session = Depends(get_db)):
    unit = InventoryUnit(**payload.model_dump())
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.get("/{unit_id}", response_model=InventoryUnitRead)
def get_inventory_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)):
    unit = db.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory unit not found")
    return unit


@router.patch("/{unit_id}", response_model=InventoryUnitRead)
def update_inventory_unit(unit_id: uuid.UUID, payload: InventoryUnitUpdate, db: Session = Depends(get_db)):
    unit = db.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory unit not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    db.commit()
    db.refresh(unit)
    return unit


@router.post("/{unit_id}/archive", response_model=InventoryUnitRead)
def archive_inventory_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)):
    unit = db.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory unit not found")
    unit.status = InventoryUnitStatus.archived
    db.commit()
    db.refresh(unit)
    return unit


@router.post("/{unit_id}/adjustments", response_model=InventoryUnitRead)
def create_adjustment(unit_id: uuid.UUID, payload: InventoryAdjustmentCreate, db: Session = Depends(get_db)):
    unit = db.get(InventoryUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory unit not found")
    adjustment = InventoryAdjustment(
        inventory_unit_id=unit.id,
        adjustment_type=payload.adjustment_type,
        quantity_delta=payload.quantity_delta,
        reason=payload.reason,
    )
    db.add(adjustment)
    unit.quantity = float(unit.quantity) + payload.quantity_delta
    db.commit()
    db.refresh(unit)
    return unit
