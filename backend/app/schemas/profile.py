import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

THEME_VALUES = ("system", "light", "dark")


class ProfileRead(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_data_url: str | None = None
    theme: str


class ProfileUpdate(BaseModel):
    avatar_data_url: str | None = Field(default=None, max_length=2_000_000)
    theme: str | None = None
