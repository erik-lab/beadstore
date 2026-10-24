import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# base64 inflates by ~4/3, so this admits a file of roughly the service's
# 15MB processing limit.
MAX_IMAGE_BASE64_CHARS = 21 * 1024 * 1024


class ProductImageUpload(BaseModel):
    """One photo, base64-encoded in JSON.

    Matches how the order-email scan and inventory import already submit
    files, and keeps python-multipart out of the dependency list.
    """

    filename: str = Field(default="", max_length=255)
    data_base64: str = Field(min_length=1, max_length=MAX_IMAGE_BASE64_CHARS)
    alt_text: str | None = None


class ProductImageUpdate(BaseModel):
    alt_text: str | None = None


class ProductImageReorder(BaseModel):
    """Image ids in the order they should appear, first being the primary."""

    image_ids: list[uuid.UUID] = Field(min_length=1)


class ProductImageRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    content_type: str
    byte_size: int
    width: int | None
    height: int | None
    sort_order: int
    original_filename: str | None
    alt_text: str | None
    created_at: datetime
    # Where to fetch the image. Either this API's own endpoint, or a CDN URL
    # when the bucket is public — the client just uses whatever it's given.
    url: str
    # True for the first image, which is what Etsy shows in search results.
    is_primary: bool

    # storage_key and checksum are deliberately absent: internal details the
    # client has no use for, and the key is the one value that shouldn't be
    # echoed back out where it could be fed to a storage call.
