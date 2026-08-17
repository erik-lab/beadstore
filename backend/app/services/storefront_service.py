import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.catalog_listing import CatalogListing
from app.models.enums import AvailableQuantityMode, CatalogListingStatus, SaleChannel
from app.models.sale import Sale
from app.schemas.sale import SaleCreate, SaleLineInput
from app.schemas.storefront import StorefrontListingRead, StorefrontOrderCreate
from app.services.catalog_service import attach_derived_availability, attach_derived_availability_many
from app.services.sales_service import create_sale


def public_available_quantity(listing: CatalogListing) -> float | None:
    if listing.available_quantity_mode == AvailableQuantityMode.manual:
        return float(listing.manual_available_quantity) if listing.manual_available_quantity is not None else None
    if listing.available_quantity_mode == AvailableQuantityMode.derived_from_inventory:
        return listing.derived_available_quantity
    return None


def _to_public_read(listing: CatalogListing) -> StorefrontListingRead:
    return StorefrontListingRead(
        id=listing.id,
        title=listing.title,
        short_description=listing.short_description,
        listing_description=listing.listing_description,
        price=listing.price,
        sales_unit=listing.sales_unit,
        available_quantity=public_available_quantity(listing),
        category_name=listing.category_override_name or listing.product.category_name,
        subtype=listing.subtype_override or listing.product.subtype_name,
        tags=listing.tags,
        collection_theme=listing.collection_theme,
        featured=listing.featured,
    )


def count_public_listings(db: Session) -> int:
    return db.query(CatalogListing).filter(CatalogListing.status == CatalogListingStatus.published).count()


def list_public_listings(db: Session, limit: int = 50, offset: int = 0) -> list[StorefrontListingRead]:
    listings = (
        db.query(CatalogListing)
        .filter(CatalogListing.status == CatalogListingStatus.published)
        .order_by(CatalogListing.sort_order, CatalogListing.title)
        .offset(offset)
        .limit(limit)
        .all()
    )
    attach_derived_availability_many(db, listings)
    return [_to_public_read(listing) for listing in listings]


def get_public_listing_or_404(db: Session, listing_id: uuid.UUID) -> StorefrontListingRead:
    listing = (
        db.query(CatalogListing)
        .filter(CatalogListing.id == listing_id, CatalogListing.status == CatalogListingStatus.published)
        .first()
    )
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    attach_derived_availability(db, listing)
    return _to_public_read(listing)


def create_storefront_order(db: Session, payload: StorefrontOrderCreate) -> Sale:
    # Price and product are always resolved from our own published listing,
    # never trusted from the caller — a storefront (or anything spoofing one)
    # only ever gets to say *what* and *how many*, not what it costs.
    sale_lines: list[SaleLineInput] = []
    for line in payload.lines:
        listing = (
            db.query(CatalogListing)
            .filter(
                CatalogListing.id == line.catalog_listing_id,
                CatalogListing.status == CatalogListingStatus.published,
            )
            .first()
        )
        if listing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {line.catalog_listing_id} not found",
            )
        sale_lines.append(
            SaleLineInput(
                product_id=listing.product_id,
                catalog_listing_id=listing.id,
                quantity=line.quantity,
                unit_price=listing.price,
            )
        )

    return create_sale(
        db,
        SaleCreate(
            channel=SaleChannel.storefront,
            external_order_id=payload.external_order_id,
            notes=payload.notes,
            lines=sale_lines,
        ),
    )
