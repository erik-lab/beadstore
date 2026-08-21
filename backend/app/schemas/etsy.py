import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EtsyAccountStatus, EtsySyncStatus
from app.schemas.common import ORMModel


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


class EtsyListingSyncRead(ORMModel):
    id: uuid.UUID
    catalog_listing_id: uuid.UUID
    etsy_shop_id: str
    etsy_listing_id: str | None
    sync_status: EtsySyncStatus
    last_synced_at: datetime | None
    last_error: str | None


class EtsyPullResult(BaseModel):
    created: int
    skipped_unmapped: int
    skipped_duplicate: int


class EtsySimulateSaleRequest(BaseModel):
    catalog_listing_id: uuid.UUID
    quantity: float = Field(default=1, gt=0)
    price: float | None = Field(default=None, ge=0)
