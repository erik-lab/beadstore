import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import IntakeBatchStatus, IntakeConfidence, IntakeRowStatus, IntakeSourceKind
from app.schemas.common import ORMModel

# Roughly the per-request ceiling the extractor enforces on file text; applied
# to pasted/dictated text too so one path can't bypass the other's limit.
MAX_SOURCE_CHARS = 120_000
# base64 inflates by ~4/3, so this allows a file of about 7MB.
MAX_FILE_BASE64_CHARS = 10 * 1024 * 1024


class IntakeParseTextRequest(BaseModel):
    """Parse typed, pasted or dictated text."""

    text: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)
    # `voice` marks text that came from browser dictation. It changes nothing
    # about how the text is parsed — it's recorded so the batch list can show
    # where an import came from.
    source_kind: IntakeSourceKind = IntakeSourceKind.paste
    source_name: str | None = Field(default=None, max_length=255)

    @field_validator("source_kind")
    @classmethod
    def text_sources_only(cls, value: IntakeSourceKind) -> IntakeSourceKind:
        if value not in (IntakeSourceKind.paste, IntakeSourceKind.voice):
            raise ValueError("Text imports must be 'paste' or 'voice'; upload files to the file endpoint.")
        return value


class IntakeParseFileRequest(BaseModel):
    """Parse an uploaded file.

    Sent as base64 in JSON rather than multipart, matching how the order-email
    scan already submits attachments and keeping python-multipart out of the
    dependency list.
    """

    filename: str = Field(default="", max_length=255)
    mime_type: str = Field(default="", max_length=120)
    data_base64: str = Field(min_length=1, max_length=MAX_FILE_BASE64_CHARS)


class IntakeRowUpdate(BaseModel):
    """A reviewer's edit to one draft row. Only the sent fields change."""

    product_name: str | None = None
    category_name: str | None = None
    subtype_name: str | None = None
    matched_product_id: uuid.UUID | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit_type: str | None = None
    unit_cost: float | None = Field(default=None, ge=0)
    vendor_name: str | None = None
    location_name: str | None = None
    received_date: date | None = None
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = None
    notes: str | None = None
    attributes: dict[str, str] | None = None


class IntakeBulkUpdate(BaseModel):
    """Values applied to every not-yet-committed row in a batch."""

    vendor_name: str | None = None
    location_name: str | None = None
    received_date: date | None = None
    category_name: str | None = None
    unit_type: str | None = None


class IntakeRowSkip(BaseModel):
    skipped: bool = True


class IntakeRowRead(ORMModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    row_index: int
    raw_fragment: str | None
    product_name: str | None
    category_name: str | None
    subtype_name: str | None
    matched_product_id: uuid.UUID | None
    matched_product_name: str | None = None
    quantity: float | None
    unit_type: str | None
    unit_cost: float | None
    vendor_name: str | None
    location_name: str | None
    received_date: date | None
    sku: str | None
    description: str | None
    notes: str | None
    attributes: dict[str, str]
    # Which required fields are still empty — the review screen's gap flags.
    missing_fields: list[str] = Field(validation_alias="missing_field_names")
    confidence: IntakeConfidence
    status: IntakeRowStatus
    commit_error: str | None
    created_product_id: uuid.UUID | None
    created_inventory_unit_id: uuid.UUID | None


class IntakeBatchRead(ORMModel):
    id: uuid.UUID
    source_kind: IntakeSourceKind
    source_name: str | None
    status: IntakeBatchStatus
    parser_notes: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class NamesToCreate(BaseModel):
    """Master data a commit would add, shown for confirmation beforehand."""

    categories: list[str] = Field(default_factory=list)
    vendors: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)


class IntakeBatchDetail(IntakeBatchRead):
    raw_text: str | None
    rows: list[IntakeRowRead] = Field(default_factory=list)
    will_create: NamesToCreate = Field(default_factory=NamesToCreate)


class IntakeCommitResult(BaseModel):
    batch_id: uuid.UUID
    committed: int
    failed: int
    remaining: int
    batch_status: IntakeBatchStatus
