import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.enums import PurchaseOrderStatus
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderDetailRead,
    PurchaseOrderLineCreate,
    PurchaseOrderLineRead,
    PurchaseOrderLineUpdate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PurchaseOrderRead])
def list_purchase_orders(
    db: Session = Depends(get_db),
    vendor_id: uuid.UUID | None = None,
    status_filter: PurchaseOrderStatus | None = Query(default=None, alias="status"),
    open_only: bool = False,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    query = db.query(PurchaseOrder)
    if vendor_id:
        query = query.filter(PurchaseOrder.vendor_id == vendor_id)
    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)
    if open_only:
        query = query.filter(
            PurchaseOrder.status.in_(
                [PurchaseOrderStatus.draft, PurchaseOrderStatus.submitted, PurchaseOrderStatus.partially_received]
            )
        )
    return query.order_by(PurchaseOrder.order_date.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=PurchaseOrderDetailRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(payload: PurchaseOrderCreate, db: Session = Depends(get_db)):
    po = PurchaseOrder(
        vendor_id=payload.vendor_id,
        order_date=payload.order_date or date.today(),
        expected_date=payload.expected_date,
        notes=payload.notes,
        status=PurchaseOrderStatus.draft,
    )
    db.add(po)
    db.flush()
    for line in payload.lines:
        db.add(PurchaseOrderLine(purchase_order_id=po.id, **line.model_dump()))
    db.commit()
    db.refresh(po)
    return _with_lines(db, po)


def _with_lines(db: Session, po: PurchaseOrder) -> PurchaseOrder:
    db.refresh(po)
    _ = po.lines  # trigger load
    return po


@router.get("/{po_id}", response_model=PurchaseOrderDetailRead)
def get_purchase_order(po_id: uuid.UUID, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


@router.patch("/{po_id}", response_model=PurchaseOrderDetailRead)
def update_purchase_order(po_id: uuid.UUID, payload: PurchaseOrderUpdate, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(po, field, value)
    db.commit()
    db.refresh(po)
    return po


@router.post("/{po_id}/mark-ordered", response_model=PurchaseOrderDetailRead)
def mark_purchase_order_ordered(po_id: uuid.UUID, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    po.status = PurchaseOrderStatus.submitted
    db.commit()
    db.refresh(po)
    return po


@router.post("/{po_id}/cancel", response_model=PurchaseOrderDetailRead)
def cancel_purchase_order(po_id: uuid.UUID, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    po.status = PurchaseOrderStatus.cancelled
    db.commit()
    db.refresh(po)
    return po


@router.post("/{po_id}/lines", response_model=PurchaseOrderLineRead, status_code=status.HTTP_201_CREATED)
def add_purchase_order_line(po_id: uuid.UUID, payload: PurchaseOrderLineCreate, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    line = PurchaseOrderLine(purchase_order_id=po.id, **payload.model_dump())
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.patch("/lines/{line_id}", response_model=PurchaseOrderLineRead)
def update_purchase_order_line(line_id: uuid.UUID, payload: PurchaseOrderLineUpdate, db: Session = Depends(get_db)):
    line = db.get(PurchaseOrderLine, line_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order line not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    db.commit()
    db.refresh(line)
    return line


@router.post("/lines/{line_id}/cancel", response_model=PurchaseOrderLineRead)
def cancel_purchase_order_line(line_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models.enums import PurchaseOrderLineStatus

    line = db.get(PurchaseOrderLine, line_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order line not found")
    line.status = PurchaseOrderLineStatus.cancelled
    db.commit()
    db.refresh(line)
    return line
