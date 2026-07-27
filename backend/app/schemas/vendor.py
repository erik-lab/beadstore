import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ActiveArchivedStatus
from app.schemas.common import ORMModel


class VendorCreate(BaseModel):
    name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class VendorUpdate(BaseModel):
    name: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    status: ActiveArchivedStatus | None = None


class VendorRead(ORMModel):
    id: uuid.UUID
    name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    notes: str | None
    status: ActiveArchivedStatus
    created_at: datetime
    updated_at: datetime
