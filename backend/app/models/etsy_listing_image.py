"""Which of a product's photos are on Etsy, and in what order.

Etsy assigns each uploaded image its own id and a rank, where rank 1 is the
one shown in search results. There's no "set the rank of an existing image"
call, so the only way to change order is to re-upload — which means the app
has to know what it previously sent, or every push would either duplicate
images or leave the order wrong.

One row per (listing sync, product image) actually uploaded. The checksum is
copied from the product image at upload time so a replaced photo is
recognisable as different even if nothing else about the row changed.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class EtsyListingImage(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "etsy_listing_images"
    __table_args__ = (
        UniqueConstraint(
            "etsy_listing_sync_id", "product_image_id", name="uq_etsy_listing_images_sync_image"
        ),
    )

    etsy_listing_sync_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("etsy_listing_syncs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # No cascade from product_images on purpose: when a photo is deleted
    # locally the row has to survive long enough for the next push to tell
    # Etsy to delete its copy. The push clears it afterwards.
    product_image_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_images.id", ondelete="SET NULL"), nullable=True
    )
    etsy_image_id: Mapped[str] = mapped_column(String(50), nullable=False)
    # Etsy's own rank: 1 is the primary image.
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    sync: Mapped["EtsyListingSync"] = relationship(viewonly=True)  # noqa: F821
