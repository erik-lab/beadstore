import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ReceivingStatus, UnitType
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class Receipt(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "receipts"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["ReceiptLine"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")


class ReceiptLine(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "receipt_lines"

    receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receipts.id"), nullable=False)
    purchase_order_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_order_lines.id"), nullable=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    unresolved_item_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    received_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    received_unit_type: Mapped[UnitType] = mapped_column(
        Enum(UnitType, native_enum=False, length=20), nullable=False
    )
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    receiving_status: Mapped[ReceivingStatus] = mapped_column(
        Enum(ReceivingStatus, native_enum=False, length=20), nullable=False
    )
    discrepancy_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    inventory_unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inventory_units.id"), nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    receipt: Mapped[Receipt] = relationship(back_populates="lines")
