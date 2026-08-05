from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Profile(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # A small user-uploaded image, stored as a data: URL (resized client-side
    # before upload) rather than a file on disk — simplest option for a
    # handful of internal users and avoids needing separate blob storage.
    avatar_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "system" | "light" | "dark" — "system" defers to the browser's
    # prefers-color-scheme, the other two are an explicit override.
    theme: Mapped[str] = mapped_column(String(10), nullable=False, default="system", server_default="system")
