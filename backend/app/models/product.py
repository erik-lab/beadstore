import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ActiveArchivedStatus, ImageStatus, ProductSourceType
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin
from app.models.product_category import ProductCategory, ProductSubtype


class Product(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_categories.id"), nullable=False)
    subtype_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_subtypes.id"), nullable=True)
    # Free-text subtype captured when "Other" is chosen in the subtype picker,
    # instead of formally adding a one-off row to the shared subtype list.
    custom_subtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    manufacturing_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    design_motif: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hole_configuration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cut_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    source_type: Mapped[ProductSourceType] = mapped_column(
        Enum(ProductSourceType, native_enum=False, length=20),
        default=ProductSourceType.purchased,
        nullable=False,
    )

    category: Mapped[ProductCategory] = relationship(viewonly=True, lazy="joined")
    subtype: Mapped[ProductSubtype | None] = relationship(viewonly=True, lazy="joined")

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    @property
    def subtype_name(self) -> str | None:
        if self.subtype:
            return self.subtype.name
        return self.custom_subtype
