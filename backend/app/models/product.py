import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import ActiveArchivedStatus, ImageStatus
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class Product(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_categories.id"), nullable=False)
    subtype_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_subtypes.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shape: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finish: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hole_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strand_length: Mapped[str | None] = mapped_column(String(100), nullable=True)
    count: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attributes_json: Mapped[str | None] = mapped_column(String, nullable=True)

    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_status: Mapped[ImageStatus] = mapped_column(
        Enum(ImageStatus, native_enum=False, length=20), default=ImageStatus.none, nullable=False
    )
    media_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[ActiveArchivedStatus] = mapped_column(
        Enum(ActiveArchivedStatus, native_enum=False, length=20),
        default=ActiveArchivedStatus.active,
        nullable=False,
    )
