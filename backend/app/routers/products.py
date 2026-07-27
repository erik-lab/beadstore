import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.catalog_listing import CatalogListing
from app.models.enums import ActiveArchivedStatus
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.schemas.catalog_listing import CatalogListingRead
from app.schemas.inventory_unit import InventoryUnitRead
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_user)])


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
    query = db.query(Product)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if subtype_id:
        query = query.filter(Product.subtype_id == subtype_id)
    if status_filter:
        query = query.filter(Product.status == status_filter)
    return query.order_by(Product.name).offset(offset).limit(limit).all()


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: uuid.UUID, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/archive", response_model=ProductRead)
def archive_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product.status = ActiveArchivedStatus.archived
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}/inventory-units", response_model=list[InventoryUnitRead])
def get_product_inventory_units(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(InventoryUnit).filter(InventoryUnit.product_id == product_id).all()


@router.get("/{product_id}/catalog-listings", response_model=list[CatalogListingRead])
def get_product_catalog_listings(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(CatalogListing).filter(CatalogListing.product_id == product_id).all()
