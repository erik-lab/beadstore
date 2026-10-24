"""Photos attached to a product.

A separate table rather than more columns on `products` because a product has
several photos and their order matters: Etsy takes up to ten per listing and
treats the first as the one shown in search results. The existing
`products.image_url` / `image_status` / `media_notes` columns predate this and
were never wired to anything — they stay for now rather than being dropped as
a side effect of this work.

Rows hold a storage key, not a URL. Where the bytes live is the storage
backend's business (see app/core/storage.py), and a stored URL would go stale
the moment the bucket or CDN changes.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin
from app.models.product import Product


class ProductImage(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "product_images"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_product_images_storage_key"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Path within the bucket, e.g. "products/<product id>/<image id>.jpg".
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Lowest sort_order is the primary image. One ordering column rather than
    # an `is_primary` flag as well — two sources of truth for "which is
    # first" is how they end up disagreeing.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # sha256 of the stored bytes, so re-uploading the same photo can be
    # spotted instead of silently duplicated.
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Etsy accepts alt text per image, and it's what a screen reader reads.
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped[Product] = relationship(viewonly=True)
