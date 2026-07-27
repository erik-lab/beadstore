from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import ActiveArchivedStatus
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class Vendor(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "vendors"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[ActiveArchivedStatus] = mapped_column(
        Enum(ActiveArchivedStatus, native_enum=False, length=20),
        default=ActiveArchivedStatus.active,
        nullable=False,
    )
