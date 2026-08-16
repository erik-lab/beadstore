import uuid

from pydantic import BaseModel

from app.schemas.common import NonBlankStr, ORMModel


class ProductCategoryCreate(BaseModel):
    name: NonBlankStr


class ProductCategoryUpdate(BaseModel):
    name: NonBlankStr


class ProductCategoryRead(ORMModel):
    id: uuid.UUID
    name: str


class ProductSubtypeCreate(BaseModel):
    category_id: uuid.UUID
    name: NonBlankStr


class ProductSubtypeUpdate(BaseModel):
    name: NonBlankStr


class ProductSubtypeRead(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
