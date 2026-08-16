import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.catalog_listing import CatalogListing
from app.models.enums import AvailableQuantityMode, CatalogListingStatus, InventoryUnitStatus
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.schemas.catalog_listing import CatalogListingCreate, CatalogListingUpdate


def compute_derived_available_quantity(db: Session, listing: CatalogListing) -> int | None:
    """How many of `listing` could be sold right now, from on-hand inventory.

    Only meaningful when available_quantity_mode is derived_from_inventory —
    None otherwise (manual/not_tracked listings don't have this concept).
    `quantity_per_listing` is how many physical units one sale of this
    listing consumes (e.g. a "set of 10 beads" listing against beads sold
    individually in inventory); defaults to 1 when unset. This does not yet
    account for stock already claimed by *other* listings/channels selling
    the same product — see docs/design/api-tiers-work-plan.md Phase 1 notes;
    that needs the reservation concept that doesn't exist yet.
    """
    if listing.available_quantity_mode != AvailableQuantityMode.derived_from_inventory:
        return None

    on_hand = (
        db.query(func.sum(InventoryUnit.quantity))
        .filter(InventoryUnit.product_id == listing.product_id, InventoryUnit.status == InventoryUnitStatus.available)
        .scalar()
    ) or 0

    per_listing = float(listing.quantity_per_listing) if listing.quantity_per_listing else 1
    if per_listing <= 0:
        return 0
    return math.floor(float(on_hand) / per_listing)


def attach_derived_availability(db: Session, listing: CatalogListing) -> CatalogListing:
    listing.derived_available_quantity = compute_derived_available_quantity(db, listing)
    return listing


def attach_derived_availability_many(db: Session, listings: list[CatalogListing]) -> list[CatalogListing]:
    for listing in listings:
        attach_derived_availability(db, listing)
    return listings


def list_catalog_listings(
    db: Session,
    search: str | None = None,
    product_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CatalogListing]:
    query = db.query(CatalogListing)
    if search:
        pattern = f"%{search}%"
        query = query.outerjoin(Product, CatalogListing.product_id == Product.id).filter(
            or_(
                CatalogListing.title.ilike(pattern),
                CatalogListing.listing_description.ilike(pattern),
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
            )
        )
    if product_id:
        query = query.filter(CatalogListing.product_id == product_id)
    listings = query.order_by(CatalogListing.title).offset(offset).limit(limit).all()
    return attach_derived_availability_many(db, listings)


def create_catalog_listing(db: Session, payload: CatalogListingCreate) -> CatalogListing:
    listing = CatalogListing(**payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return attach_derived_availability(db, listing)


def get_catalog_listing_or_404(db: Session, listing_id: uuid.UUID) -> CatalogListing:
    listing = db.get(CatalogListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog listing not found")
    return attach_derived_availability(db, listing)


def update_catalog_listing(db: Session, listing_id: uuid.UUID, payload: CatalogListingUpdate) -> CatalogListing:
    listing = db.get(CatalogListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog listing not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)
    db.commit()
    db.refresh(listing)
    return attach_derived_availability(db, listing)


def archive_catalog_listing(db: Session, listing_id: uuid.UUID) -> CatalogListing:
    listing = db.get(CatalogListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog listing not found")
    listing.status = CatalogListingStatus.archived
    db.commit()
    db.refresh(listing)
    return attach_derived_availability(db, listing)
