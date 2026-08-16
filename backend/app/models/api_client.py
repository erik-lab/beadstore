from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import ApiClientKind, ApiClientStatus
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ApiClient(UUIDPKMixin, TimestampMixin, Base):
    """A non-human API credential — for a future storefront app or the Etsy
    integration, not for staff (staff auth is Supabase, see core/security.py).

    Only the key's hash is stored; the raw key is generated and shown once,
    at creation time, by the router — see core/api_keys.py.
    """

    __tablename__ = "api_clients"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[ApiClientKind] = mapped_column(Enum(ApiClientKind, native_enum=False, length=20), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[ApiClientStatus] = mapped_column(
        Enum(ApiClientStatus, native_enum=False, length=20), default=ApiClientStatus.active, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
