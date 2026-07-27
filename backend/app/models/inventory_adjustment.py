import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import InventoryAdjustmentType
from app.models.mixins import TimestampMixin, UUIDPKMixin, utcnow


class InventoryAdjustment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_adjustments"

    inventory_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_units.id"), nullable=False)
    adjustment_type: Mapped[InventoryAdjustmentType] = mapped_column(
        Enum(InventoryAdjustmentType, native_enum=False, length=30), nullable=False
    )
    quantity_delta: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    adjusted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    adjusted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
