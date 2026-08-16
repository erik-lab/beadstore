import uuid

from pydantic import BaseModel

from app.schemas.common import NonBlankStr, ORMModel


class HintCreate(BaseModel):
    page: NonBlankStr
    item_key: NonBlankStr
    text: NonBlankStr


class HintUpdate(BaseModel):
    page: NonBlankStr | None = None
    item_key: NonBlankStr | None = None
    text: NonBlankStr | None = None


class HintUpsert(BaseModel):
    text: NonBlankStr


class HintRead(ORMModel):
    id: uuid.UUID
    page: str
    item_key: str
    text: str
