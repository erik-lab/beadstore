import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import SaleStatus, UnitType
from app.schemas.common import Page


class StorefrontListingRead(BaseModel):
    """Public-safe view of a catalog listing — deliberately its own schema,
    not CatalogListingRead, so a field only meant for staff (cost, vendor,
    internal notes, workflow status) can't leak out here just because it got
    added to the internal schema later. Only ever built from a *published*
    listing — see services/storefront_service.py.
    """

    id: uuid.UUID
    title: str
    short_description: str | None
    listing_description: str | None
    price: float | None
    sales_unit: UnitType | None
    available_quantity: float | None
    category_name: str | None = None
    subtype: str | None = None
    tags: str | None
    collection_theme: str | None
    featured: bool


class StorefrontListingPage(Page):
    items: list[StorefrontListingRead]


class StorefrontOrderLineInput(BaseModel):
    catalog_listing_id: uuid.UUID
    quantity: float = Field(gt=0)


class StorefrontOrderCreate(BaseModel):
    external_order_id: str | None = None
    notes: str | None = None
    lines: list[StorefrontOrderLineInput] = Field(min_length=1)


class StorefrontOrderRead(BaseModel):
    id: uuid.UUID
    status: SaleStatus
    sale_date: date
