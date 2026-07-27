from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Hint(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "hints"
    __table_args__ = (UniqueConstraint("page", "item_key", name="uq_hints_page_item_key"),)

    page: Mapped[str] = mapped_column(String(100), nullable=False)
    item_key: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
