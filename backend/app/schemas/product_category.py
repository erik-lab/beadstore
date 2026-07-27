import uuid

from pydantic import BaseModel

from app.schemas.common import ORMModel


class ProductCategoryCreate(BaseModel):
    name: str


class ProductCategoryRead(ORMModel):
    id: uuid.UUID
    name: str


class ProductSubtypeCreate(BaseModel):
    category_id: uuid.UUID
    name: str


class ProductSubtypeRead(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
