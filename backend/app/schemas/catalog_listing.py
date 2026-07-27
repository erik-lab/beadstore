import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AvailableQuantityMode, CatalogListingStatus, PublishReadiness, UnitType
from app.schemas.common import ORMModel


class CatalogListingCreate(BaseModel):
    product_id: uuid.UUID
    title: str
    short_description: str | None = None
    listing_description: str | None = None
    price: float | None = None
    status: CatalogListingStatus = CatalogListingStatus.draft

    sales_unit: UnitType | None = None
    quantity_per_listing: float | None = None
    available_quantity_mode: AvailableQuantityMode = AvailableQuantityMode.not_tracked
    manual_available_quantity: float | None = None

    category_override_id: uuid.UUID | None = None
    subtype_override: str | None = None
    tags: str | None = None
    collection_theme: str | None = None

    featured: bool = False
    sort_order: int = 0

    seo_title: str | None = None
    seo_description: str | None = None
    listing_notes: str | None = None
    publish_readiness: PublishReadiness | None = None


class CatalogListingUpdate(BaseModel):
    title: str | None = None
    short_description: str | None = None
    listing_description: str | None = None
    price: float | None = None
    status: CatalogListingStatus | None = None

    sales_unit: UnitType | None = None
    quantity_per_listing: float | None = None
    available_quantity_mode: AvailableQuantityMode | None = None
    manual_available_quantity: float | None = None

    category_override_id: uuid.UUID | None = None
    subtype_override: str | None = None
    tags: str | None = None
    collection_theme: str | None = None

    featured: bool | None = None
    sort_order: int | None = None

    seo_title: str | None = None
    seo_description: str | None = None
    listing_notes: str | None = None
    publish_readiness: PublishReadiness | None = None


class CatalogListingRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    title: str
    short_description: str | None
    listing_description: str | None
    price: float | None
    status: CatalogListingStatus

    sales_unit: UnitType | None
    quantity_per_listing: float | None
    available_quantity_mode: AvailableQuantityMode
    manual_available_quantity: float | None

    category_override_id: uuid.UUID | None
    category_override_name: str | None = None
    subtype_override: str | None
    tags: str | None
    collection_theme: str | None

    featured: bool
    sort_order: int

    seo_title: str | None
    seo_description: str | None
    listing_notes: str | None
    publish_readiness: PublishReadiness | None

    product_name: str | None = None
    product_description: str | None = None
    product_sku: str | None = None

    created_at: datetime
    updated_at: datetime
