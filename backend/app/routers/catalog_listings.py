import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.catalog_listing import CatalogListing
from app.models.product import Product
from app.schemas.catalog_listing import CatalogListingCreate, CatalogListingRead, CatalogListingUpdate

router = APIRouter(prefix="/catalog-listings", tags=["catalog-listings"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CatalogListingRead])
def list_catalog_listings(
    db: Session = Depends(get_db),
    search: str | None = None,
    product_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
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
    return query.order_by(CatalogListing.title).offset(offset).limit(limit).all()


@router.post("", response_model=CatalogListingRead, status_code=status.HTTP_201_CREATED)
def create_catalog_listing(payload: CatalogListingCreate, db: Session = Depends(get_db)):
    listing = CatalogListing(**payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/{listing_id}", response_model=CatalogListingRead)
def get_catalog_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    listing = db.get(CatalogListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog listing not found")
    return listing


@router.patch("/{listing_id}", response_model=CatalogListingRead)
def update_catalog_listing(listing_id: uuid.UUID, payload: CatalogListingUpdate, db: Session = Depends(get_db)):
    listing = db.get(CatalogListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog listing not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)
    db.commit()
    db.refresh(listing)
    return listing


@router.post("/{listing_id}/archive", response_model=CatalogListingRead)
def archive_catalog_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models.enums import CatalogListingStatus

    listing = db.get(CatalogListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog listing not found")
    listing.status = CatalogListingStatus.archived
    db.commit()
    db.refresh(listing)
    return listing
