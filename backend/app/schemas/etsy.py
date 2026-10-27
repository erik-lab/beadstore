import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EtsyAccountStatus, EtsySyncStatus
from app.schemas.common import ORMModel


class EtsyOption(BaseModel):
    """One pickable Etsy-side value — a shipping profile, return policy or
    taxonomy category. The id is Etsy's own numeric id, as a string, and the
    label is what the dropdown shows.
    """

    id: str
    label: str


class EtsyAccountRead(ORMModel):
    id: uuid.UUID
    shop_id: str
    shop_name: str | None
    scopes: str
    status: EtsyAccountStatus
    created_at: datetime


class EtsyConnectUrlResponse(BaseModel):
    url: str


class EtsyPushRequest(BaseModel):
    taxonomy_id: int | None = None
    shipping_profile_id: int | None = None
    return_policy_id: int | None = None
    who_made: str | None = None
    when_made: str | None = None
    is_supply: bool | None = None


class EtsyListingImageRead(ORMModel):
    """One photo as it exists on Etsy for a listing. rank 1 is primary."""

    id: uuid.UUID
    product_image_id: uuid.UUID | None
    etsy_image_id: str
    rank: int


class EtsyActivateResult(BaseModel):
    catalog_listing_id: uuid.UUID
    etsy_listing_id: str | None
    etsy_state: str | None


class EtsyListingSyncRead(ORMModel):
    id: uuid.UUID
    catalog_listing_id: uuid.UUID
    etsy_shop_id: str
    etsy_listing_id: str | None
    sync_status: EtsySyncStatus
    last_synced_at: datetime | None
    last_error: str | None
    etsy_state: str | None = None


class EtsyPullResult(BaseModel):
    created: int
    skipped_unmapped: int
    skipped_duplicate: int


class EtsySimulateSaleRequest(BaseModel):
    catalog_listing_id: uuid.UUID
    quantity: float = Field(default=1, gt=0)
    price: float | None = Field(default=None, ge=0)
