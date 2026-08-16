import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ActiveArchivedStatus, ImageStatus, ProductSourceType
from app.schemas.common import NonBlankStr, ORMModel


class ProductAttributes(BaseModel):
    material: str | None = None
    color: str | None = None
    size: str | None = None
    shape: str | None = None
    finish: str | None = None
    hole_size: str | None = None
    origin: str | None = None
    strand_length: str | None = None
    count: str | None = None
    grade: str | None = None
    condition: str | None = None
    manufacturing_method: str | None = None
    design_motif: str | None = None
    hole_configuration: str | None = None
    cut_style: str | None = None
    attributes_json: str | None = None


class ProductCreate(ProductAttributes):
    name: NonBlankStr
    category_id: uuid.UUID
    subtype_id: uuid.UUID | None = None
    custom_subtype: str | None = None
    description: str | None = None
    sku: str | None = None
    image_url: str | None = None
    image_status: ImageStatus = ImageStatus.none
    media_notes: str | None = None
    source_type: ProductSourceType = ProductSourceType.purchased


class ProductUpdate(BaseModel):
    name: NonBlankStr | None = None
    category_id: uuid.UUID | None = None
    subtype_id: uuid.UUID | None = None
    custom_subtype: str | None = None
    description: str | None = None
    sku: str | None = None
    material: str | None = None
    color: str | None = None
    size: str | None = None
    shape: str | None = None
    finish: str | None = None
    hole_size: str | None = None
    origin: str | None = None
    strand_length: str | None = None
    count: str | None = None
    grade: str | None = None
    condition: str | None = None
    manufacturing_method: str | None = None
    design_motif: str | None = None
    hole_configuration: str | None = None
    cut_style: str | None = None
    attributes_json: str | None = None
    image_url: str | None = None
    image_status: ImageStatus | None = None
    media_notes: str | None = None
    status: ActiveArchivedStatus | None = None
    source_type: ProductSourceType | None = None


class ProductRead(ORMModel):
    id: uuid.UUID
    name: str
    category_id: uuid.UUID
    category_name: str | None = None
    subtype_id: uuid.UUID | None
    subtype_name: str | None = None
    custom_subtype: str | None = None
    description: str | None
    sku: str | None
    material: str | None
    color: str | None
    size: str | None
    shape: str | None
    finish: str | None
    hole_size: str | None
    origin: str | None
    strand_length: str | None
    count: str | None
    grade: str | None
    condition: str | None
    manufacturing_method: str | None
    design_motif: str | None
    hole_configuration: str | None
    cut_style: str | None
    attributes_json: str | None
    image_url: str | None
    image_status: ImageStatus
    media_notes: str | None
    status: ActiveArchivedStatus
    source_type: ProductSourceType
    created_at: datetime
    updated_at: datetime
