import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import PurchaseOrderLineStatus, PurchaseOrderStatus, UnitType
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class PurchaseOrder(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "purchase_orders"

    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, native_enum=False, length=30),
        default=PurchaseOrderStatus.draft,
        nullable=False,
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_retroactive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "purchase_order_lines"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    expected_item_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expected_quantity: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    expected_unit_type: Mapped[UnitType | None] = mapped_column(
        Enum(UnitType, native_enum=False, length=20), nullable=True
    )
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[PurchaseOrderLineStatus] = mapped_column(
        Enum(PurchaseOrderLineStatus, native_enum=False, length=30),
        default=PurchaseOrderLineStatus.expected,
        nullable=False,
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
