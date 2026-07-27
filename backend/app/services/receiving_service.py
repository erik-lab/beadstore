import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import (
    InventoryUnitStatus,
    PurchaseOrderLineStatus,
    PurchaseOrderStatus,
    ReceivingStatus,
)
from app.models.inventory_unit import InventoryUnit
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.receipt import Receipt, ReceiptLine
from app.models.vendor import Vendor
from app.schemas.receiving import QuickReceivePayload, ReceiveLineInput, ReceivePayload

UNKNOWN_VENDOR_NAME = "Unknown Vendor"


def get_or_create_unknown_vendor(db: Session) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.name == UNKNOWN_VENDOR_NAME).first()
    if vendor is None:
        vendor = Vendor(name=UNKNOWN_VENDOR_NAME)
        db.add(vendor)
        db.flush()
    return vendor


def _cumulative_received_for_line(db: Session, purchase_order_line_id: uuid.UUID) -> float:
    total = (
        db.query(ReceiptLine)
        .filter(
            ReceiptLine.purchase_order_line_id == purchase_order_line_id,
            ReceiptLine.voided_at.is_(None),
        )
        .with_entities(ReceiptLine.received_quantity)
        .all()
    )
    return sum(float(qty) for (qty,) in total)


def _determine_status(
    line_input: ReceiveLineInput, expected_line: PurchaseOrderLine | None, previously_received_qty: float = 0.0
) -> ReceivingStatus:
    if line_input.receiving_status is not None:
        return line_input.receiving_status
    if expected_line is None:
        return ReceivingStatus.unresolved if line_input.product_id is None else ReceivingStatus.matched
    if expected_line.product_id is not None and line_input.product_id is not None and (
        expected_line.product_id != line_input.product_id
    ):
        return ReceivingStatus.substitution
    if expected_line.expected_quantity is None:
        return ReceivingStatus.matched
    expected_qty = float(expected_line.expected_quantity)
    received_qty = previously_received_qty + float(line_input.received_quantity)
    if received_qty < expected_qty:
        return ReceivingStatus.shortage
    if received_qty > expected_qty:
        return ReceivingStatus.overage
    return ReceivingStatus.matched


def _create_inventory_unit_for_line(
    db: Session,
    *,
    product_id: uuid.UUID | None,
    unresolved_description: str | None,
    quantity: float,
    unit_type,
    received_date: date,
    unit_cost: float | None,
    vendor_id: uuid.UUID,
    purchase_order_id: uuid.UUID,
    location_id: uuid.UUID | None,
    damaged: bool,
) -> InventoryUnit:
    inv_status = InventoryUnitStatus.damaged if damaged else (
        InventoryUnitStatus.unresolved if product_id is None else InventoryUnitStatus.available
    )
    unit = InventoryUnit(
        product_id=product_id,
        unresolved_description=unresolved_description,
        quantity=quantity,
        unit_type=unit_type,
        status=inv_status,
        received_date=received_date,
        cost_amount=unit_cost,
        vendor_id=vendor_id,
        purchase_order_id=purchase_order_id,
        location_id=location_id,
    )
    db.add(unit)
    db.flush()
    return unit


def _update_line_and_po_status(db: Session, po: PurchaseOrder) -> None:
    db.flush()
    lines = po.lines
    if not lines:
        return
    statuses = {line.status for line in lines}
    if statuses <= {PurchaseOrderLineStatus.cancelled}:
        po.status = PurchaseOrderStatus.cancelled
    elif statuses <= {PurchaseOrderLineStatus.received, PurchaseOrderLineStatus.cancelled}:
        po.status = PurchaseOrderStatus.received
    elif any(
        s in (PurchaseOrderLineStatus.received, PurchaseOrderLineStatus.partially_received, PurchaseOrderLineStatus.discrepancy)
        for s in statuses
    ):
        po.status = PurchaseOrderStatus.partially_received
    db.flush()


def receive_against_order(
    db: Session, purchase_order_id: uuid.UUID, payload: ReceivePayload, user_id: str | None
) -> Receipt:
    po = db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    if po.status in (PurchaseOrderStatus.cancelled, PurchaseOrderStatus.closed):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot receive against a purchase order with status '{po.status.value}'",
        )

    receipt = Receipt(
        purchase_order_id=po.id,
        received_date=payload.received_date or date.today(),
        notes=payload.notes,
        received_by=uuid.UUID(user_id) if user_id else None,
    )
    db.add(receipt)
    db.flush()

    lines_by_id = {line.id: line for line in po.lines}

    for line_input in payload.lines:
        expected_line = lines_by_id.get(line_input.purchase_order_line_id) if line_input.purchase_order_line_id else None
        previously_received = (
            _cumulative_received_for_line(db, expected_line.id) if expected_line is not None else 0.0
        )
        receiving_status = _determine_status(line_input, expected_line, previously_received)
        damaged = receiving_status == ReceivingStatus.damaged

        inventory_unit = None
        if line_input.received_quantity and line_input.received_quantity > 0:
            inventory_unit = _create_inventory_unit_for_line(
                db,
                product_id=line_input.product_id or (expected_line.product_id if expected_line else None),
                unresolved_description=line_input.unresolved_item_description,
                quantity=line_input.received_quantity,
                unit_type=line_input.received_unit_type,
                received_date=receipt.received_date,
                unit_cost=line_input.unit_cost or (expected_line.unit_cost if expected_line else None),
                vendor_id=po.vendor_id,
                purchase_order_id=po.id,
                location_id=line_input.location_id,
                damaged=damaged,
            )

        receipt_line = ReceiptLine(
            receipt_id=receipt.id,
            purchase_order_line_id=expected_line.id if expected_line else None,
            product_id=line_input.product_id or (expected_line.product_id if expected_line else None),
            unresolved_item_description=line_input.unresolved_item_description,
            received_quantity=line_input.received_quantity,
            received_unit_type=line_input.received_unit_type,
            unit_cost=line_input.unit_cost,
            receiving_status=receiving_status,
            discrepancy_notes=line_input.discrepancy_notes,
            inventory_unit_id=inventory_unit.id if inventory_unit else None,
            location_id=line_input.location_id,
        )
        db.add(receipt_line)

        if expected_line is not None:
            cumulative_received = previously_received + float(line_input.received_quantity)
            if receiving_status in (
                ReceivingStatus.substitution,
                ReceivingStatus.damaged,
                ReceivingStatus.unresolved,
            ):
                expected_line.status = PurchaseOrderLineStatus.discrepancy
            elif expected_line.expected_quantity is not None and cumulative_received < float(
                expected_line.expected_quantity
            ):
                expected_line.status = PurchaseOrderLineStatus.partially_received
            else:
                expected_line.status = PurchaseOrderLineStatus.received

    _update_line_and_po_status(db, po)
    db.commit()
    db.refresh(receipt)
    return receipt


def quick_receive(db: Session, payload: QuickReceivePayload, user_id: str | None) -> Receipt:
    vendor = db.get(Vendor, payload.vendor_id)
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    received_date = payload.received_date or date.today()

    po = PurchaseOrder(
        vendor_id=vendor.id,
        status=PurchaseOrderStatus.received,
        order_date=received_date,
        is_retroactive=True,
        notes="Created automatically during receiving (no prior order).",
    )
    db.add(po)
    db.flush()

    receipt = Receipt(
        purchase_order_id=po.id,
        received_date=received_date,
        notes=payload.notes,
        received_by=uuid.UUID(user_id) if user_id else None,
    )
    db.add(receipt)
    db.flush()

    for line_input in payload.lines:
        po_line = PurchaseOrderLine(
            purchase_order_id=po.id,
            product_id=line_input.product_id,
            expected_item_description=line_input.unresolved_item_description,
            expected_quantity=line_input.received_quantity,
            expected_unit_type=line_input.received_unit_type,
            unit_cost=line_input.unit_cost,
            status=PurchaseOrderLineStatus.received,
        )
        db.add(po_line)
        db.flush()

        inventory_unit = _create_inventory_unit_for_line(
            db,
            product_id=line_input.product_id,
            unresolved_description=line_input.unresolved_item_description,
            quantity=line_input.received_quantity,
            unit_type=line_input.received_unit_type,
            received_date=received_date,
            unit_cost=line_input.unit_cost,
            vendor_id=vendor.id,
            purchase_order_id=po.id,
            location_id=line_input.location_id,
            damaged=False,
        )

        receipt_line = ReceiptLine(
            receipt_id=receipt.id,
            purchase_order_line_id=po_line.id,
            product_id=line_input.product_id,
            unresolved_item_description=line_input.unresolved_item_description,
            received_quantity=line_input.received_quantity,
            received_unit_type=line_input.received_unit_type,
            unit_cost=line_input.unit_cost,
            receiving_status=ReceivingStatus.unresolved if line_input.product_id is None else ReceivingStatus.matched,
            inventory_unit_id=inventory_unit.id,
            location_id=line_input.location_id,
        )
        db.add(receipt_line)

    db.commit()
    db.refresh(receipt)
    return receipt


def resolve_receipt_line(db: Session, receipt_line: ReceiptLine, product_id: uuid.UUID) -> ReceiptLine:
    receipt_line.product_id = product_id
    receipt_line.unresolved_item_description = None
    if receipt_line.receiving_status == ReceivingStatus.unresolved:
        receipt_line.receiving_status = ReceivingStatus.matched
    if receipt_line.inventory_unit_id:
        unit = db.get(InventoryUnit, receipt_line.inventory_unit_id)
        if unit is not None:
            unit.product_id = product_id
            unit.unresolved_description = None
            if unit.status == InventoryUnitStatus.unresolved:
                unit.status = InventoryUnitStatus.available
    db.commit()
    db.refresh(receipt_line)
    return receipt_line
