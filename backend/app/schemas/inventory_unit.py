import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import InventoryAdjustmentType, InventoryUnitStatus, UnitType
from app.schemas.common import ORMModel


class InventoryUnitCreate(BaseModel):
    product_id: uuid.UUID | None = None
    unresolved_description: str | None = None
    quantity: float = Field(gt=0)
    unit_type: UnitType
    status: InventoryUnitStatus = InventoryUnitStatus.available
    received_date: date
    cost_amount: float | None = Field(default=None, ge=0)
    cost_currency: str | None = None
    vendor_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_product_or_description(self):
        if self.product_id is None and not self.unresolved_description:
            raise ValueError("Either product_id or unresolved_description is required")
        return self


class InventoryUnitUpdate(BaseModel):
    product_id: uuid.UUID | None = None
    unresolved_description: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit_type: UnitType | None = None
    status: InventoryUnitStatus | None = None
    received_date: date | None = None
    cost_amount: float | None = Field(default=None, ge=0)
    cost_currency: str | None = None
    vendor_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    notes: str | None = None


class InventoryUnitRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str | None = None
    product_sku: str | None = None
    unresolved_description: str | None
    quantity: float
    unit_type: UnitType
    status: InventoryUnitStatus
    received_date: date
    cost_amount: float | None
    cost_currency: str | None
    vendor_id: uuid.UUID | None
    vendor_name: str | None = None
    purchase_order_id: uuid.UUID | None
    receipt_line_id: uuid.UUID | None
    receipt_received_date: date | None = None
    location_id: uuid.UUID | None
    location_name: str | None = None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InventoryAdjustmentCreate(BaseModel):
    adjustment_type: InventoryAdjustmentType
    quantity_delta: float
    reason: str | None = None

    @field_validator("quantity_delta")
    @classmethod
    def quantity_delta_nonzero(cls, value: float) -> float:
        if value == 0:
            raise ValueError("quantity_delta must not be zero — a zero adjustment is a no-op")
        return value
