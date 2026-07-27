import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.product_category import ProductCategory, ProductSubtype
from app.schemas.product_category import (
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductSubtypeCreate,
    ProductSubtypeRead,
    ProductSubtypeUpdate,
)

router = APIRouter(prefix="/product-categories", tags=["product-categories"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ProductCategoryRead])
def list_categories(db: Session = Depends(get_db)):
    return db.query(ProductCategory).order_by(ProductCategory.name).all()


@router.post("", response_model=ProductCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: ProductCategoryCreate, db: Session = Depends(get_db)):
    category = ProductCategory(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=ProductCategoryRead)
def rename_category(category_id: uuid.UUID, payload: ProductCategoryUpdate, db: Session = Depends(get_db)):
    category = db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    category.name = payload.name
    db.commit()
    db.refresh(category)
    return category


@router.get("/{category_id}/subtypes", response_model=list[ProductSubtypeRead])
def list_subtypes(category_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(ProductSubtype)
        .filter(ProductSubtype.category_id == category_id)
        .order_by(ProductSubtype.name)
        .all()
    )


subtype_router = APIRouter(prefix="/product-subtypes", tags=["product-categories"], dependencies=[Depends(get_current_user)])


@subtype_router.post("", response_model=ProductSubtypeRead, status_code=status.HTTP_201_CREATED)
def create_subtype(payload: ProductSubtypeCreate, db: Session = Depends(get_db)):
    category = db.get(ProductCategory, payload.category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    subtype = ProductSubtype(**payload.model_dump())
    db.add(subtype)
    db.commit()
    db.refresh(subtype)
    return subtype


@subtype_router.patch("/{subtype_id}", response_model=ProductSubtypeRead)
def rename_subtype(subtype_id: uuid.UUID, payload: ProductSubtypeUpdate, db: Session = Depends(get_db)):
    subtype = db.get(ProductSubtype, subtype_id)
    if subtype is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtype not found")
    subtype.name = payload.name
    db.commit()
    db.refresh(subtype)
    return subtype
