import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ActiveArchivedStatus
from app.schemas.common import ORMModel


class LocationCreate(BaseModel):
    name: str
    description: str | None = None
    parent_location_id: uuid.UUID | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_location_id: uuid.UUID | None = None
    status: ActiveArchivedStatus | None = None


class LocationRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    parent_location_id: uuid.UUID | None
    status: ActiveArchivedStatus
    created_at: datetime
    updated_at: datetime
