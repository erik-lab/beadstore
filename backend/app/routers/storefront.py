import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_api_client_kind
from app.models.enums import ApiClientKind
from app.schemas.sale import SaleDetailRead
from app.schemas.storefront import (
    StorefrontListingPage,
    StorefrontListingRead,
    StorefrontOrderCreate,
)
from app.services import sales_service, storefront_service

# The first real business-data router on the API-key auth path (see
# core/security.py, /api-access/whoami). Scoped to storefront keys only —
# an Etsy-kind key gets a 403 here even if somehow presented, since the two
# integrations shouldn't be interchangeable just because both are "not
# staff."
router = APIRouter(
    prefix="/storefront",
    tags=["storefront"],
    dependencies=[Depends(require_api_client_kind(ApiClientKind.storefront))],
)


@router.get("/listings", response_model=StorefrontListingPage)
def list_listings(db: Session = Depends(get_db), limit: int = Query(default=50, le=200), offset: int = 0):
    items = storefront_service.list_public_listings(db, limit=limit, offset=offset)
    total = storefront_service.count_public_listings(db)
    return StorefrontListingPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/listings/{listing_id}", response_model=StorefrontListingRead)
def get_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    return storefront_service.get_public_listing_or_404(db, listing_id)


@router.post("/orders", response_model=SaleDetailRead, status_code=status.HTTP_201_CREATED)
def create_order(payload: StorefrontOrderCreate, db: Session = Depends(get_db)):
    return storefront_service.create_storefront_order(db, payload)
