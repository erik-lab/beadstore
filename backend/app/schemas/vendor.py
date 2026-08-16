import re
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.enums import ActiveArchivedStatus
from app.schemas.common import NonBlankStr, ORMModel

# Deliberately permissive (not RFC 5322): just enough to catch typos like a
# missing "@" or domain before they end up in a vendor record the order-email
# matching feature relies on, without rejecting anything a real address
# could legitimately look like.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str | None) -> str | None:
    if value is not None and not _EMAIL_PATTERN.match(value):
        raise ValueError("Not a valid email address")
    return value


class VendorCreate(BaseModel):
    name: NonBlankStr
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None

    _validate_email = field_validator("email")(_validate_email)


class VendorUpdate(BaseModel):
    name: NonBlankStr | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    status: ActiveArchivedStatus | None = None

    _validate_email = field_validator("email")(_validate_email)


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
