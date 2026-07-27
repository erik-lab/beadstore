import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import ActiveArchivedStatus
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class Location(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    status: Mapped[ActiveArchivedStatus] = mapped_column(
        Enum(ActiveArchivedStatus, native_enum=False, length=20),
        default=ActiveArchivedStatus.active,
        nullable=False,
    )
