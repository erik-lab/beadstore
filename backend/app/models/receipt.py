import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ReceivingStatus, UnitType
from app.models.location import Location
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder


class Receipt(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "receipts"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["ReceiptLine"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")
    purchase_order: Mapped[PurchaseOrder] = relationship(viewonly=True, lazy="joined")


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
    product: Mapped[Product | None] = relationship(viewonly=True, lazy="joined")
    location: Mapped[Location | None] = relationship(viewonly=True, lazy="joined")

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def product_sku(self) -> str | None:
        return self.product.sku if self.product else None

    @property
    def location_name(self) -> str | None:
        return self.location.name if self.location else None

    @property
    def purchase_order_id(self) -> uuid.UUID:
        return self.receipt.purchase_order_id

    @property
    def received_date(self) -> date:
        return self.receipt.received_date

    @property
    def vendor_name(self) -> str | None:
        return self.receipt.purchase_order.vendor_name
