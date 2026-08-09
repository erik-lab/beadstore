from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class AttributeOption(UUIDPKMixin, TimestampMixin, Base):
    """A suggested pick-list value for a product attribute field.

    Seeds the "hybrid pick list" (see products router ATTRIBUTE_FIELDS) with
    values that don't yet exist on any actual Product row, e.g. from an
    imported taxonomy, so the dropdown is useful before real inventory exists
    for every value.
    """

    __tablename__ = "attribute_options"
    __table_args__ = (UniqueConstraint("field", "value", name="uq_attribute_options_field_value"),)

    field: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(String(150), nullable=False)
