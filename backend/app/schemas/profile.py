import uuid

from app.schemas.common import ORMModel


class ProfileRead(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
