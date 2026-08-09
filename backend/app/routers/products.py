import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Column, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.attribute_option import AttributeOption
from app.models.catalog_listing import CatalogListing
from app.models.enums import ActiveArchivedStatus
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.models.purchase_order import PurchaseOrderLine
from app.models.receipt import ReceiptLine
from app.schemas.catalog_listing import CatalogListingRead
from app.schemas.inventory_unit import InventoryUnitRead
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.schemas.purchase_order import PurchaseOrderLineRead
from app.schemas.receiving import ReceiptLineRead

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_user)])

# Optional attribute fields eligible for the "hybrid pick list" (type-ahead of
# previously used values, or type a new one). Whitelisted explicitly rather
# than accepting an arbitrary column name from the client.
ATTRIBUTE_FIELDS: dict[str, Column] = {
    "material": Product.material,
    "color": Product.color,
    "size": Product.size,
    "shape": Product.shape,
    "finish": Product.finish,
    "hole_size": Product.hole_size,
    "origin": Product.origin,
    "strand_length": Product.strand_length,
    "count": Product.count,
    "grade": Product.grade,
    "condition": Product.condition,
    "manufacturing_method": Product.manufacturing_method,
    "design_motif": Product.design_motif,
    "hole_configuration": Product.hole_configuration,
    "cut_style": Product.cut_style,
}


@router.get("/attribute-options", response_model=list[str])
def get_attribute_options(db: Session = Depends(get_db), field: str = Query(...)):
    column = ATTRIBUTE_FIELDS.get(field)
    if column is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown attribute field '{field}'")
    rows = (
        db.query(column)
        .filter(column.isnot(None), column != "")
        .distinct()
        .all()
    )
    values = {value for (value,) in rows}
    seeded = db.query(AttributeOption.value).filter(AttributeOption.field == field).all()
    values.update(value for (value,) in seeded)
    return sorted(values)


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
        pattern = f"%{search}%"
        searchable_columns = [
            Product.name,
            Product.sku,
            Product.description,
            *ATTRIBUTE_FIELDS.values(),
        ]
        query = query.filter(or_(*(column.ilike(pattern) for column in searchable_columns)))
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


@router.get("/{product_id}/purchase-order-lines", response_model=list[PurchaseOrderLineRead])
def get_product_purchase_order_lines(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Supplier order lines that requested this product — 'which order(s) is this coming from'."""
    return (
        db.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.product_id == product_id)
        .order_by(PurchaseOrderLine.created_at.desc())
        .all()
    )


@router.get("/{product_id}/receipt-lines", response_model=list[ReceiptLineRead])
def get_product_receipt_lines(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Receiving history for this product — 'how did this stock get here'."""
    return (
        db.query(ReceiptLine)
        .filter(ReceiptLine.product_id == product_id)
        .order_by(ReceiptLine.created_at.desc())
        .all()
    )
