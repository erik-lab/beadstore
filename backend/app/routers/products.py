import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.enums import ActiveArchivedStatus
from app.schemas.catalog_listing import CatalogListingRead
from app.schemas.inventory_unit import InventoryUnitRead
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.schemas.purchase_order import PurchaseOrderLineRead
from app.schemas.receiving import ReceiptLineRead
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_user)])


@router.get("/attribute-options", response_model=list[str])
def get_attribute_options(db: Session = Depends(get_db), field: str = Query(...)):
    return product_service.get_attribute_options(db, field)


@router.get("", response_model=list[ProductRead])
def list_products(
    db: Session = Depends(get_db),
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    subtype_id: uuid.UUID | None = None,
    status_filter: ActiveArchivedStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    return product_service.list_products(
        db,
        search=search,
        category_id=category_id,
        subtype_id=subtype_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    return product_service.create_product(db, payload)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return product_service.get_product_or_404(db, product_id)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: uuid.UUID, payload: ProductUpdate, db: Session = Depends(get_db)):
    return product_service.update_product(db, product_id, payload)


@router.post("/{product_id}/archive", response_model=ProductRead)
def archive_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return product_service.archive_product(db, product_id)


@router.get("/{product_id}/inventory-units", response_model=list[InventoryUnitRead])
def get_product_inventory_units(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return product_service.get_product_inventory_units(db, product_id)


@router.get("/{product_id}/catalog-listings", response_model=list[CatalogListingRead])
def get_product_catalog_listings(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return product_service.get_product_catalog_listings(db, product_id)


@router.get("/{product_id}/purchase-order-lines", response_model=list[PurchaseOrderLineRead])
def get_product_purchase_order_lines(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Supplier order lines that requested this product — 'which order(s) is this coming from'."""
    return product_service.get_product_purchase_order_lines(db, product_id)


@router.get("/{product_id}/receipt-lines", response_model=list[ReceiptLineRead])
def get_product_receipt_lines(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Receiving history for this product — 'how did this stock get here'."""
    return product_service.get_product_receipt_lines(db, product_id)
