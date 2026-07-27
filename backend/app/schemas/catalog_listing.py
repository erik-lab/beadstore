import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CatalogListingStatus
from app.schemas.common import ORMModel


class CatalogListingCreate(BaseModel):
    product_id: uuid.UUID
    title: str
    listing_description: str | None = None
    price: float | None = None
    status: CatalogListingStatus = CatalogListingStatus.draft


class CatalogListingUpdate(BaseModel):
    title: str | None = None
    listing_description: str | None = None
    price: float | None = None
    status: CatalogListingStatus | None = None


class CatalogListingRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    title: str
    listing_description: str | None
    price: float | None
    status: CatalogListingStatus
    created_at: datetime
    updated_at: datetime
