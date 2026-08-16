import uuid

from fastapi import HTTPException, status
from sqlalchemy import Column, or_
from sqlalchemy.orm import Session

from app.models.attribute_option import AttributeOption
from app.models.catalog_listing import CatalogListing
from app.models.enums import ActiveArchivedStatus
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.models.purchase_order import PurchaseOrderLine
from app.models.receipt import ReceiptLine
from app.schemas.product import ProductCreate, ProductUpdate

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


def get_attribute_options(db: Session, field: str) -> list[str]:
    column = ATTRIBUTE_FIELDS.get(field)
    if column is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown attribute field '{field}'")
    rows = db.query(column).filter(column.isnot(None), column != "").distinct().all()
    values = {value for (value,) in rows}
    seeded = db.query(AttributeOption.value).filter(AttributeOption.field == field).all()
    values.update(value for (value,) in seeded)
    return sorted(values)


def list_products(
    db: Session,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    subtype_id: uuid.UUID | None = None,
    status_filter: ActiveArchivedStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Product]:
    query = db.query(Product)
    if search:
        pattern = f"%{search}%"
        searchable_columns = [Product.name, Product.sku, Product.description, *ATTRIBUTE_FIELDS.values()]
        query = query.filter(or_(*(column.ilike(pattern) for column in searchable_columns)))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if subtype_id:
        query = query.filter(Product.subtype_id == subtype_id)
    if status_filter:
        query = query.filter(Product.status == status_filter)
    return query.order_by(Product.name).offset(offset).limit(limit).all()


def create_product(db: Session, payload: ProductCreate) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_product_or_404(db: Session, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def update_product(db: Session, product_id: uuid.UUID, payload: ProductUpdate) -> Product:
    product = get_product_or_404(db, product_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def archive_product(db: Session, product_id: uuid.UUID) -> Product:
    product = get_product_or_404(db, product_id)
    product.status = ActiveArchivedStatus.archived
    db.commit()
    db.refresh(product)
    return product


def get_product_inventory_units(db: Session, product_id: uuid.UUID) -> list[InventoryUnit]:
    return db.query(InventoryUnit).filter(InventoryUnit.product_id == product_id).all()


def get_product_catalog_listings(db: Session, product_id: uuid.UUID) -> list[CatalogListing]:
    from app.services.catalog_service import attach_derived_availability_many

    listings = db.query(CatalogListing).filter(CatalogListing.product_id == product_id).all()
    return attach_derived_availability_many(db, listings)


def get_product_purchase_order_lines(db: Session, product_id: uuid.UUID) -> list[PurchaseOrderLine]:
    return (
        db.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.product_id == product_id)
        .order_by(PurchaseOrderLine.created_at.desc())
        .all()
    )


def get_product_receipt_lines(db: Session, product_id: uuid.UUID) -> list[ReceiptLine]:
    return (
        db.query(ReceiptLine)
        .filter(ReceiptLine.product_id == product_id)
        .order_by(ReceiptLine.created_at.desc())
        .all()
    )
