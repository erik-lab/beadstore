from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Shop(UUIDPKMixin, TimestampMixin, Base):
    """The future top-level tenant boundary. Nothing references this yet —
    it exists now (with exactly one row) so that eventually scoping the rest
    of the schema to it is a backfill + not-null + FK migration, rather than
    inventing the concept from scratch. See engagement notes on multi-tenancy
    for why this is deliberately minimal (no RLS, no billing, no per-shop
    settings) until there's a second real shop to design against.
    """

    __tablename__ = "shops"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
