import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.catalog_listing import CatalogListing
from app.models.enums import EtsySyncStatus
from app.models.mixins import TimestampMixin, UUIDPKMixin


class EtsyListingSync(UUIDPKMixin, TimestampMixin, Base):
    """Tracks one catalog listing's push state to Etsy, plus the
    Etsy-required listing fields (taxonomy, shipping profile, ...) that have
    no home on CatalogListing itself — those are Etsy's own quirks, not part
    of our core domain, so they're kept contained here rather than leaking
    onto the shared model. One row per catalog listing that's ever been
    pushed (or is staged to be).
    """

    __tablename__ = "etsy_listing_syncs"
    __table_args__ = (UniqueConstraint("catalog_listing_id", name="uq_etsy_listing_syncs_catalog_listing"),)

    catalog_listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalog_listings.id"), nullable=False)
    etsy_shop_id: Mapped[str] = mapped_column(String(50), nullable=False)
    etsy_listing_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sync_status: Mapped[EtsySyncStatus] = mapped_column(
        Enum(EtsySyncStatus, native_enum=False, length=20), default=EtsySyncStatus.not_synced, nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)

    # Etsy-required fields for createDraftListing — see
    # https://developers.etsy.com/documentation/reference/#operation/createDraftListing
    taxonomy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    return_policy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    who_made: Mapped[str | None] = mapped_column(String(20), nullable=True)
    when_made: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    catalog_listing: Mapped[CatalogListing] = relationship(viewonly=True, lazy="joined")
