import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.enums import PurchaseOrderLineStatus, PurchaseOrderStatus, UnitType
from app.schemas.common import ORMModel


class PurchaseOrderLineCreate(BaseModel):
    product_id: uuid.UUID | None = None
    expected_item_description: str | None = None
    expected_quantity: float | None = None
    expected_unit_type: UnitType | None = None
    unit_cost: float | None = None

    @model_validator(mode="after")
    def require_product_or_description(self):
        if self.product_id is None and not self.expected_item_description:
            raise ValueError("Either product_id or expected_item_description is required")
        return self


class PurchaseOrderLineUpdate(BaseModel):
    product_id: uuid.UUID | None = None
    expected_item_description: str | None = None
    expected_quantity: float | None = None
    expected_unit_type: UnitType | None = None
    unit_cost: float | None = None
    status: PurchaseOrderLineStatus | None = None


class PurchaseOrderLineRead(ORMModel):
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str | None = None
    product_sku: str | None = None
    expected_item_description: str | None
    expected_quantity: float | None
    expected_unit_type: UnitType | None
    unit_cost: float | None
    status: PurchaseOrderLineStatus
    order_date: date | None = None
    vendor_name: str | None = None


class PurchaseOrderCreate(BaseModel):
    vendor_id: uuid.UUID
    order_date: date | None = None
    expected_date: date | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineCreate] = []


class PurchaseOrderUpdate(BaseModel):
    vendor_id: uuid.UUID | None = None
    status: PurchaseOrderStatus | None = None
    order_date: date | None = None
    expected_date: date | None = None
    notes: str | None = None


class PurchaseOrderRead(ORMModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str | None = None
    status: PurchaseOrderStatus
    order_date: date
    expected_date: date | None
    is_retroactive: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PurchaseOrderDetailRead(PurchaseOrderRead):
    lines: list[PurchaseOrderLineRead] = []
