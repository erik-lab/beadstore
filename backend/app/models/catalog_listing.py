import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import AvailableQuantityMode, CatalogListingStatus, PublishReadiness, UnitType
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin
from app.models.product import Product
from app.models.product_category import ProductCategory


class CatalogListing(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "catalog_listings"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_description: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[CatalogListingStatus] = mapped_column(
        Enum(CatalogListingStatus, native_enum=False, length=20),
        default=CatalogListingStatus.draft,
        nullable=False,
    )

    sales_unit: Mapped[UnitType | None] = mapped_column(Enum(UnitType, native_enum=False, length=20), nullable=True)
    quantity_per_listing: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    available_quantity_mode: Mapped[AvailableQuantityMode] = mapped_column(
        Enum(AvailableQuantityMode, native_enum=False, length=30),
        default=AvailableQuantityMode.not_tracked,
        nullable=False,
    )
    manual_available_quantity: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)

    category_override_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id"), nullable=True
    )
    subtype_override: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    collection_theme: Mapped[str | None] = mapped_column(String(150), nullable=True)

    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    publish_readiness: Mapped[PublishReadiness | None] = mapped_column(
        Enum(PublishReadiness, native_enum=False, length=30), nullable=True
    )

    product: Mapped[Product] = relationship(viewonly=True, lazy="joined")
    category_override: Mapped[ProductCategory | None] = relationship(viewonly=True, lazy="joined")

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def product_description(self) -> str | None:
        return self.product.description if self.product else None

    @property
    def product_sku(self) -> str | None:
        return self.product.sku if self.product else None

    @property
    def category_override_name(self) -> str | None:
        return self.category_override.name if self.category_override else None
