import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import InventoryUnitStatus, UnitType
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class InventoryUnit(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "inventory_units"

    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    unresolved_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit_type: Mapped[UnitType] = mapped_column(Enum(UnitType, native_enum=False, length=20), nullable=False)
    status: Mapped[InventoryUnitStatus] = mapped_column(
        Enum(InventoryUnitStatus, native_enum=False, length=20),
        default=InventoryUnitStatus.available,
        nullable=False,
    )
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    cost_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    receipt_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("receipt_lines.id", use_alter=True, name="fk_inventory_units_receipt_line_id"), nullable=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
