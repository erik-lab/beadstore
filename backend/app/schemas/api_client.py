import uuid
from datetime import datetime

from app.models.enums import ApiClientKind, ApiClientStatus
from app.schemas.common import NonBlankStr, ORMModel


class ApiClientCreate(ORMModel):
    name: NonBlankStr
    kind: ApiClientKind


class ApiClientRead(ORMModel):
    id: uuid.UUID
    name: str
    kind: ApiClientKind
    status: ApiClientStatus
    last_used_at: datetime | None
    created_at: datetime


class ApiClientCreated(ApiClientRead):
    # Only ever present in the create response — the raw key is not
    # recoverable afterward, only the hash is stored.
    api_key: str


class ApiClientWhoAmI(ORMModel):
    id: uuid.UUID
    name: str
    kind: ApiClientKind
