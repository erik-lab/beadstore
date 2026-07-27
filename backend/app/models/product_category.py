import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ProductCategory(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    subtypes: Mapped[list["ProductSubtype"]] = relationship(back_populates="category")


class ProductSubtype(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_subtypes"

    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    category: Mapped[ProductCategory] = relationship(back_populates="subtypes")
