from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import EtsyAccountStatus
from app.models.mixins import TimestampMixin, UUIDPKMixin


class EtsyAccount(UUIDPKMixin, TimestampMixin, Base):
    """A connected Etsy shop — same shape/intent as EmailAccount (see
    app/models/email_account.py): the refresh token is the only long-lived
    secret, stored encrypted, and access tokens are minted fresh from it
    right before use rather than persisted.
    """

    __tablename__ = "etsy_accounts"

    shop_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    shop_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # Space-separated granted scopes, e.g. "listings_r listings_w transactions_r" —
    # recorded so we can tell at a glance whether a reconnect is needed for a
    # scope added after the original authorization.
    scopes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[EtsyAccountStatus] = mapped_column(
        Enum(EtsyAccountStatus, native_enum=False, length=20), default=EtsyAccountStatus.active, nullable=False
    )
