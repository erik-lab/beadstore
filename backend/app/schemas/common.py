from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    total: int
    limit: int
    offset: int


# A required "name"/"title"-type string: whitespace-trimmed, and rejected if
# that leaves nothing — catches "" and "   " alike, which plain `str` lets
# through and which would otherwise show up as a blank row in a pick list.
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
