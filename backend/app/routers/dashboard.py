import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.enums import ActiveArchivedStatus, PurchaseOrderStatus, ReceivingStatus
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.receipt import Receipt, ReceiptLine
from app.schemas.inventory_unit import InventoryUnitRead
from app.schemas.purchase_order import PurchaseOrderRead
from app.schemas.receiving import ReceiptLineRead

router = APIRouter(prefix="/operations", tags=["operations"], dependencies=[Depends(get_current_user)])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    active_products = db.query(func.count(Product.id)).filter(Product.status == ActiveArchivedStatus.active).scalar()
    inventory_on_hand = (
        db.query(func.count(InventoryUnit.id))
        .filter(InventoryUnit.status.in_(["available", "reserved"]))
        .scalar()
    )
    open_orders = (
        db.query(func.count(PurchaseOrder.id))
        .filter(
            PurchaseOrder.status.in_(
                [PurchaseOrderStatus.draft, PurchaseOrderStatus.submitted, PurchaseOrderStatus.partially_received]
            )
        )
        .scalar()
    )
    unresolved_items = (
        db.query(func.count(InventoryUnit.id)).filter(InventoryUnit.status == "unresolved").scalar()
    )
    discrepancies = (
        db.query(func.count(ReceiptLine.id))
        .filter(
            ReceiptLine.receiving_status.in_(
                [
                    ReceivingStatus.shortage,
                    ReceivingStatus.overage,
                    ReceivingStatus.substitution,
                    ReceivingStatus.damaged,
                    ReceivingStatus.unresolved,
                ]
            )
        )
        .scalar()
    )
    recently_received = db.query(func.count(Receipt.id)).scalar()
    return {
        "active_products": active_products,
        "inventory_on_hand": inventory_on_hand,
        "open_orders": open_orders,
        "unresolved_items": unresolved_items,
        "receiving_discrepancies": discrepancies,
        "total_receipts": recently_received,
    }


@router.get("/open-orders", response_model=list[PurchaseOrderRead])
def open_orders(db: Session = Depends(get_db)):
    return (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.status.in_(
                [PurchaseOrderStatus.draft, PurchaseOrderStatus.submitted, PurchaseOrderStatus.partially_received]
            )
        )
        .order_by(PurchaseOrder.order_date.desc())
        .all()
    )


@router.get("/unresolved-items", response_model=list[InventoryUnitRead])
def unresolved_items(db: Session = Depends(get_db)):
    return db.query(InventoryUnit).filter(InventoryUnit.status == "unresolved").all()


@router.get("/inventory-on-hand", response_model=list[InventoryUnitRead])
def inventory_on_hand(
    db: Session = Depends(get_db),
    category_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID | None = None,
):
    query = db.query(InventoryUnit).filter(InventoryUnit.status.in_(["available", "reserved"]))
    if location_id:
        query = query.filter(InventoryUnit.location_id == location_id)
    if vendor_id:
        query = query.filter(InventoryUnit.vendor_id == vendor_id)
    if category_id:
        query = query.join(Product, InventoryUnit.product_id == Product.id).filter(
            Product.category_id == category_id
        )
    return query.all()


@router.get("/receiving-discrepancies", response_model=list[ReceiptLineRead])
def receiving_discrepancies(db: Session = Depends(get_db)):
    return (
        db.query(ReceiptLine)
        .filter(
            ReceiptLine.receiving_status.in_(
                [
                    ReceivingStatus.shortage,
                    ReceivingStatus.overage,
                    ReceivingStatus.substitution,
                    ReceivingStatus.damaged,
                    ReceivingStatus.unresolved,
                ]
            )
        )
        .all()
    )


@router.get("/recently-received", response_model=list[ReceiptLineRead])
def recently_received(db: Session = Depends(get_db), limit: int = Query(default=20, le=100)):
    return db.query(ReceiptLine).order_by(ReceiptLine.created_at.desc()).limit(limit).all()
