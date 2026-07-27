import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.enums import ReceivingStatus, UnitType
from app.schemas.common import ORMModel


class ReceiveLineInput(BaseModel):
    purchase_order_line_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    unresolved_item_description: str | None = None
    received_quantity: float
    received_unit_type: UnitType
    unit_cost: float | None = None
    receiving_status: ReceivingStatus | None = None
    discrepancy_notes: str | None = None
    location_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def require_product_or_description(self):
        if self.product_id is None and not self.unresolved_item_description:
            raise ValueError("Either product_id or unresolved_item_description is required")
        return self


class ReceivePayload(BaseModel):
    received_date: date | None = None
    notes: str | None = None
    lines: list[ReceiveLineInput]


class QuickReceiveLineInput(BaseModel):
    product_id: uuid.UUID | None = None
    unresolved_item_description: str | None = None
    received_quantity: float
    received_unit_type: UnitType
    unit_cost: float | None = None
    location_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def require_product_or_description(self):
        if self.product_id is None and not self.unresolved_item_description:
            raise ValueError("Either product_id or unresolved_item_description is required")
        return self


class QuickReceivePayload(BaseModel):
    vendor_id: uuid.UUID
    received_date: date | None = None
    notes: str | None = None
    lines: list[QuickReceiveLineInput]


class ReceiptLineRead(ORMModel):
    id: uuid.UUID
    receipt_id: uuid.UUID
    purchase_order_line_id: uuid.UUID | None
    product_id: uuid.UUID | None
    unresolved_item_description: str | None
    received_quantity: float
    received_unit_type: UnitType
    receiving_status: ReceivingStatus
    discrepancy_notes: str | None
    inventory_unit_id: uuid.UUID | None
    location_id: uuid.UUID | None


class ReceiptRead(ORMModel):
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    received_date: date
    notes: str | None
    created_at: datetime


class ReceiptDetailRead(ReceiptRead):
    lines: list[ReceiptLineRead] = []


class ReceiveResult(BaseModel):
    receipt: ReceiptDetailRead
    purchase_order_id: uuid.UUID
    purchase_order_status: str
    summary: dict
