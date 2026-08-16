import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import SaleChannel, SaleStatus
from app.schemas.common import ORMModel


class SaleLineInput(BaseModel):
    product_id: uuid.UUID
    catalog_listing_id: uuid.UUID | None = None
    quantity: float = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)


class SaleCreate(BaseModel):
    channel: SaleChannel = SaleChannel.manual
    external_order_id: str | None = None
    sale_date: date | None = None
    notes: str | None = None
    lines: list[SaleLineInput] = Field(min_length=1)


class SaleLineRead(ORMModel):
    id: uuid.UUID
    sale_id: uuid.UUID
    catalog_listing_id: uuid.UUID | None
    product_id: uuid.UUID
    product_name: str | None = None
    product_sku: str | None = None
    quantity: float
    unit_price: float | None


class SaleRead(ORMModel):
    id: uuid.UUID
    channel: SaleChannel
    external_order_id: str | None
    sale_date: date
    status: SaleStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SaleDetailRead(SaleRead):
    lines: list[SaleLineRead] = []
