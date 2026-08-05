from sqlalchemy import Enum, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import EmailAccountStatus, EmailProvider
from app.models.mixins import TimestampMixin, UUIDPKMixin


class EmailAccount(UUIDPKMixin, TimestampMixin, Base):
    """A connected mailbox (Gmail or Outlook) that Order Email Scan can scan.

    Shared across everyone using the app, the same way vendors/locations are
    — these are the store's own operational inboxes, not a personal setting.
    The refresh token is the only long-lived secret: access tokens are always
    minted fresh from it right before use and never stored.
    """

    __tablename__ = "email_accounts"
    __table_args__ = (UniqueConstraint("provider", "email_address", name="uq_email_accounts_provider_address"),)

    provider: Mapped[EmailProvider] = mapped_column(Enum(EmailProvider, native_enum=False, length=20), nullable=False)
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EmailAccountStatus] = mapped_column(
        Enum(EmailAccountStatus, native_enum=False, length=20),
        default=EmailAccountStatus.active,
        nullable=False,
    )
