import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EmailAccountStatus, EmailProvider
from app.schemas.common import ORMModel


class EmailAccountRead(ORMModel):
    id: uuid.UUID
    provider: EmailProvider
    email_address: str
    label: str | None = None
    status: EmailAccountStatus
    created_at: datetime


class ConnectUrlResponse(BaseModel):
    url: str


class ScanRequest(BaseModel):
    vendor_names: list[str] = Field(default_factory=list)


class CandidateEmailOut(BaseModel):
    id: str
    from_address: str
    subject: str
    date: str
    snippet: str
    match_reasons: list[str]


class EmailAttachmentOut(BaseModel):
    filename: str
    mime_type: str
    base64_data: str


class EmailDetailOut(BaseModel):
    id: str
    from_address: str
    to_address: str
    subject: str
    date: str
    body_text: str
    attachments: list[EmailAttachmentOut]


class MoveEmailResult(BaseModel):
    moved: bool
    reason: str | None = None
    message: str | None = None
