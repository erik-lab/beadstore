import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import PieceCostSource, PieceCreationStatus
from app.schemas.common import ORMModel


class PieceComponentInput(BaseModel):
    inventory_unit_id: uuid.UUID
    quantity_used: float = Field(gt=0)


class PieceCreationCreate(BaseModel):
    product_id: uuid.UUID
    created_date: date | None = None
    quantity_produced: float = Field(default=1, gt=0)
    # Always wins over the component-cost estimate when provided — Patti
    # can always just type a cost, whether or not components are linked.
    creation_cost: float | None = Field(default=None, ge=0)
    notes: str | None = None
    components: list[PieceComponentInput] = Field(default_factory=list)


class PieceComponentRead(ORMModel):
    id: uuid.UUID
    inventory_unit_id: uuid.UUID
    product_name: str | None = None
    product_sku: str | None = None
    quantity_used: float
    unit_cost_at_use: float | None = None


class PieceCreationRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    product_sku: str | None = None
    created_date: date
    quantity_produced: float
    creation_cost: float | None
    cost_source: PieceCostSource
    status: PieceCreationStatus
    resulting_inventory_unit_id: uuid.UUID | None
    notes: str | None
    components: list[PieceComponentRead] = []
    created_at: datetime
