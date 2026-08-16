import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import SaleChannel, SaleStatus
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class Sale(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    """An outbound sale — the demand-side counterpart to PurchaseOrder/Receipt
    (which model the supply side). Recording one decrements inventory via
    InventoryAdjustment rows, same as piece creation does when it consumes
    components — see services/sales_service.py.
    """

    __tablename__ = "sales"

    channel: Mapped[SaleChannel] = mapped_column(
        Enum(SaleChannel, native_enum=False, length=20), default=SaleChannel.manual, nullable=False
    )
    # The other system's own order id (Etsy receipt id, storefront order
    # number, ...) — null for a manually-recorded sale with no such id.
    external_order_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[SaleStatus] = mapped_column(
        Enum(SaleStatus, native_enum=False, length=20), default=SaleStatus.recorded, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    lines: Mapped[list["SaleLine"]] = relationship(back_populates="sale", viewonly=True)


class SaleLine(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "sale_lines"

    sale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales.id"), nullable=False)
    catalog_listing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("catalog_listings.id"), nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    sale: Mapped[Sale] = relationship(back_populates="lines", viewonly=True)
    product: Mapped["Product"] = relationship(viewonly=True, lazy="joined")  # noqa: F821

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def product_sku(self) -> str | None:
        return self.product.sku if self.product else None
