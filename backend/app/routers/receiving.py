import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.purchase_order import PurchaseOrder
from app.models.receipt import Receipt, ReceiptLine
from app.schemas.receiving import (
    QuickReceivePayload,
    ReceiptDetailRead,
    ReceivePayload,
    ReceiveResult,
)
from app.services import receiving_service

router = APIRouter(tags=["receiving"], dependencies=[Depends(get_current_user)])


def _summary(receipt: Receipt) -> dict:
    summary = {"matched": 0, "overage": 0, "shortage": 0, "substitution": 0, "damaged": 0, "unresolved": 0}
    for line in receipt.lines:
        key = line.receiving_status.value
        summary[key] = summary.get(key, 0) + 1
    return summary


@router.post("/purchase-orders/{po_id}/receipts", response_model=ReceiveResult, status_code=status.HTTP_201_CREATED)
def receive_against_order(
    po_id: uuid.UUID,
    payload: ReceivePayload,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    receipt = receiving_service.receive_against_order(db, po_id, payload, current_user.id)
    po = db.get(PurchaseOrder, po_id)
    return ReceiveResult(
        receipt=receipt,
        purchase_order_id=po.id,
        purchase_order_status=po.status.value,
        summary=_summary(receipt),
    )


@router.post("/receiving/quick-receive", response_model=ReceiveResult, status_code=status.HTTP_201_CREATED)
def quick_receive(
    payload: QuickReceivePayload,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    receipt = receiving_service.quick_receive(db, payload, current_user.id)
    po = db.get(PurchaseOrder, receipt.purchase_order_id)
    return ReceiveResult(
        receipt=receipt,
        purchase_order_id=po.id,
        purchase_order_status=po.status.value,
        summary=_summary(receipt),
    )


@router.get("/purchase-orders/{po_id}/receipts", response_model=list[ReceiptDetailRead])
def list_receipts_for_order(po_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(Receipt).filter(Receipt.purchase_order_id == po_id).all()


@router.get("/receipts/{receipt_id}", response_model=ReceiptDetailRead)
def get_receipt(receipt_id: uuid.UUID, db: Session = Depends(get_db)):
    receipt = db.get(Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    return receipt


@router.patch("/receipt-lines/{line_id}/resolve", response_model=ReceiptDetailRead)
def resolve_receipt_line(line_id: uuid.UUID, product_id: uuid.UUID, db: Session = Depends(get_db)):
    line = db.get(ReceiptLine, line_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt line not found")
    receiving_service.resolve_receipt_line(db, line, product_id)
    return db.get(Receipt, line.receipt_id)
