import uuid

from pydantic import BaseModel

from app.schemas.common import ORMModel


class HintCreate(BaseModel):
    page: str
    item_key: str
    text: str


class HintUpdate(BaseModel):
    page: str | None = None
    item_key: str | None = None
    text: str | None = None


class HintUpsert(BaseModel):
    text: str


class HintRead(ORMModel):
    id: uuid.UUID
    page: str
    item_key: str
    text: str
