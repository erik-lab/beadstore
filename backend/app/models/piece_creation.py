import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import PieceCostSource, PieceCreationStatus
from app.models.inventory_unit import InventoryUnit
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin
from app.models.product import Product


class PieceCreation(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    """One "I built this" event: Patti assembling a piece (jewelry she made,
    as opposed to a product bought from a vendor) optionally out of
    component products already in inventory. Mirrors Receipt's role for
    purchased goods, but the piece is *built* rather than received, and the
    "cost" comes from the components consumed rather than a vendor's price.
    """

    __tablename__ = "piece_creations"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_produced: Mapped[float] = mapped_column(Numeric(12, 3), default=1, nullable=False)
    creation_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost_source: Mapped[PieceCostSource] = mapped_column(
        Enum(PieceCostSource, native_enum=False, length=30), nullable=False
    )
    status: Mapped[PieceCreationStatus] = mapped_column(
        Enum(PieceCreationStatus, native_enum=False, length=20),
        default=PieceCreationStatus.active,
        nullable=False,
    )
    resulting_inventory_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_units.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    product: Mapped[Product] = relationship(viewonly=True, lazy="joined")
    resulting_inventory_unit: Mapped[InventoryUnit | None] = relationship(viewonly=True, lazy="joined")
    components: Mapped[list["PieceComponent"]] = relationship(
        back_populates="piece_creation", cascade="all, delete-orphan"
    )

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def product_sku(self) -> str | None:
        return self.product.sku if self.product else None


class PieceComponent(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    """One line of a piece's bill of materials: a specific inventory lot and
    how much of it was consumed. Always references a specific InventoryUnit
    (not just a product) so the quantity consumed is unambiguous."""

    __tablename__ = "piece_components"

    piece_creation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("piece_creations.id"), nullable=False)
    inventory_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_units.id"), nullable=False)
    quantity_used: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    # Snapshotted from the inventory unit's cost_amount at the moment it was
    # consumed, so a later price change elsewhere doesn't retroactively
    # change what this piece was recorded as having cost to make.
    unit_cost_at_use: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    piece_creation: Mapped[PieceCreation] = relationship(back_populates="components")
    inventory_unit: Mapped[InventoryUnit] = relationship(viewonly=True, lazy="joined")

    @property
    def product_name(self) -> str | None:
        return self.inventory_unit.product_name if self.inventory_unit else None

    @property
    def product_sku(self) -> str | None:
        return self.inventory_unit.product_sku if self.inventory_unit else None
