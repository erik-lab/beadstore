import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import CatalogListingStatus
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class CatalogListing(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "catalog_listings"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    listing_description: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[CatalogListingStatus] = mapped_column(
        Enum(CatalogListingStatus, native_enum=False, length=20),
        default=CatalogListingStatus.draft,
        nullable=False,
    )
