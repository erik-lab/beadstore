import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.schemas.catalog_listing import CatalogListingCreate, CatalogListingRead, CatalogListingUpdate
from app.services import catalog_service

router = APIRouter(prefix="/catalog-listings", tags=["catalog-listings"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CatalogListingRead])
def list_catalog_listings(
    db: Session = Depends(get_db),
    search: str | None = None,
    product_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    return catalog_service.list_catalog_listings(db, search=search, product_id=product_id, limit=limit, offset=offset)


@router.post("", response_model=CatalogListingRead, status_code=status.HTTP_201_CREATED)
def create_catalog_listing(payload: CatalogListingCreate, db: Session = Depends(get_db)):
    return catalog_service.create_catalog_listing(db, payload)


@router.get("/{listing_id}", response_model=CatalogListingRead)
def get_catalog_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    return catalog_service.get_catalog_listing_or_404(db, listing_id)


@router.patch("/{listing_id}", response_model=CatalogListingRead)
def update_catalog_listing(listing_id: uuid.UUID, payload: CatalogListingUpdate, db: Session = Depends(get_db)):
    return catalog_service.update_catalog_listing(db, listing_id, payload)


@router.post("/{listing_id}/archive", response_model=CatalogListingRead)
def archive_catalog_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    return catalog_service.archive_catalog_listing(db, listing_id)
