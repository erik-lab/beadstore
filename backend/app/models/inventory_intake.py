"""Staging tables for inventory that arrives as unstructured source material.

Patti sources inventory from spreadsheets, supplier emails, Word docs, hand
notes and (now) dictation. Rather than one import path per format, everything
is reduced to text, parsed by the same AI pass into *proposed* records, and
parked here for review. Nothing reaches `products` or `inventory_units` until
a row is explicitly committed, so a bad parse costs an edit, not a cleanup.

A batch is one paste/upload/dictation; its rows are the proposed inventory
units. Rows keep the text fragment they came from (`raw_fragment`) so a
suspicious value can be checked against the source without digging the
original file back out.
"""
import json
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import IntakeBatchStatus, IntakeConfidence, IntakeRowStatus, IntakeSourceKind
from app.models.mixins import AuditMixin, TimestampMixin, UUIDPKMixin


class InventoryIntakeBatch(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    __tablename__ = "inventory_intake_batches"
    # Staging rows churn through edits before they mean anything; auditing
    # that would bury the entries that matter. The products and inventory
    # units a commit creates are audited as usual, which is the real record.
    # created_by/updated_by are still stamped.
    __audit__ = False

    source_kind: Mapped[IntakeSourceKind] = mapped_column(
        Enum(IntakeSourceKind, native_enum=False, length=20), nullable=False
    )
    # Filename, or something like "Dictated note" — shown in the batch list so
    # Patti can tell two same-day imports apart.
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The extracted text we actually fed the parser. Kept so a batch can be
    # re-parsed after a prompt improvement, and so the reviewer can read the
    # original wording.
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[IntakeBatchStatus] = mapped_column(
        Enum(IntakeBatchStatus, native_enum=False, length=20),
        default=IntakeBatchStatus.draft,
        nullable=False,
    )
    # Anything the parser wants to tell the reviewer about the source as a
    # whole ("prices looked like totals, not per-unit").
    parser_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    rows: Mapped[list["InventoryIntakeRow"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="InventoryIntakeRow.row_index",
    )


class InventoryIntakeRow(UUIDPKMixin, TimestampMixin, AuditMixin, Base):
    """One proposed inventory unit, pre-commit and freely editable.

    Names are stored as free text rather than foreign keys because the parser
    produces words, not IDs, and the reviewer edits words. Resolution to
    category/vendor/location/product rows happens once, at commit.

    `unit_type` is a plain string for the same reason: an invalid guess from
    the parser should survive into the review screen to be corrected, not blow
    up the insert. It's validated against UnitType at commit time.
    """

    __tablename__ = "inventory_intake_rows"
    __audit__ = False  # See InventoryIntakeBatch.

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_intake_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_index: Mapped[int] = mapped_column(nullable=False, default=0)
    raw_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)

    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    subtype_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Set when the parse (or the reviewer) ties this row to a product that
    # already exists, so committing adds stock instead of a duplicate product.
    matched_product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)

    quantity: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    unit_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Product attributes (material/color/size/...) as a JSON object, keyed by
    # the same field names as products.ATTRIBUTE_FIELDS. JSON rather than 15
    # nullable columns duplicated from `products`: these are edited as a group
    # in the review UI and never queried individually.
    attributes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Recomputed by the service on every write — never trusted from the client.
    missing_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[IntakeConfidence] = mapped_column(
        Enum(IntakeConfidence, native_enum=False, length=10),
        default=IntakeConfidence.medium,
        nullable=False,
    )
    status: Mapped[IntakeRowStatus] = mapped_column(
        Enum(IntakeRowStatus, native_enum=False, length=20),
        default=IntakeRowStatus.needs_review,
        nullable=False,
    )
    commit_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    created_inventory_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_units.id"), nullable=True
    )

    batch: Mapped[InventoryIntakeBatch] = relationship(back_populates="rows")
    # Explicit foreign_keys: there are two paths to `products` from this table
    # (the pre-commit match and the product a commit created).
    matched_product: Mapped["Product | None"] = relationship(  # noqa: F821
        viewonly=True, lazy="joined", foreign_keys=[matched_product_id]
    )

    @property
    def matched_product_name(self) -> str | None:
        """Shown in review as 'adds stock to <product>' instead of a bare ID."""
        return self.matched_product.name if self.matched_product else None

    @property
    def missing_field_names(self) -> list[str]:
        """The gap flags as a list, for the API. Stored as JSON text."""
        if not self.missing_fields:
            return []
        try:
            loaded = json.loads(self.missing_fields)
        except json.JSONDecodeError:
            return []
        return [str(name) for name in loaded] if isinstance(loaded, list) else []

    @property
    def attributes(self) -> dict[str, str]:
        if not self.attributes_json:
            return {}
        try:
            loaded = json.loads(self.attributes_json)
        except json.JSONDecodeError:
            return {}
        return {str(k): str(v) for k, v in loaded.items()} if isinstance(loaded, dict) else {}
