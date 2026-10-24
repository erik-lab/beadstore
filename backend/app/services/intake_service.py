"""Staged inventory intake: build draft rows, review them, then commit.

The design rule here is that nothing the parser produces is trusted until a
person has looked at it. Draft rows hold free text, not foreign keys, and the
mapping onto real categories/vendors/locations/products happens once — at
commit — where it can fail loudly per row.

`missing_fields` is recomputed from the row on every write and never accepted
from the client, so the review screen's gap flags can't drift out of step with
what a commit would actually require.
"""
import json
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import (
    ActiveArchivedStatus,
    IntakeBatchStatus,
    IntakeConfidence,
    IntakeRowStatus,
    IntakeSourceKind,
    ProductSourceType,
    UnitType,
)
from app.models.inventory_intake import InventoryIntakeBatch, InventoryIntakeRow
from app.models.inventory_unit import InventoryUnit
from app.models.location import Location
from app.models.product import Product
from app.models.product_category import ProductCategory, ProductSubtype
from app.models.vendor import Vendor
from app.services import sku_service
from app.services.product_service import ATTRIBUTE_FIELDS

# Product attribute columns are String(100) and the name is String(255).
# The parser can produce longer strings from a verbose source; truncating here
# keeps a long description from failing the whole row's insert.
ATTRIBUTE_MAX_LENGTH = 100
NAME_MAX_LENGTH = 255

VALID_UNIT_TYPES = {unit.value for unit in UnitType}


# --------------------------------------------------------------------------
# Gap detection
# --------------------------------------------------------------------------

def compute_missing_fields(row: InventoryIntakeRow) -> list[str]:
    """Which required-for-commit fields this row still lacks.

    Mirrors exactly what commit_batch needs, so a row with no missing fields
    is a row that will commit (barring a database-level surprise).
    """
    missing: list[str] = []

    # A row either points at an existing product or carries enough to create
    # one. Category is only needed in the second case.
    if row.matched_product_id is None:
        if not (row.product_name or "").strip():
            missing.append("product_name")
        if not (row.category_name or "").strip():
            missing.append("category_name")

    if row.quantity is None or float(row.quantity) <= 0:
        missing.append("quantity")
    if not row.unit_type or row.unit_type not in VALID_UNIT_TYPES:
        missing.append("unit_type")
    if row.received_date is None:
        missing.append("received_date")

    return missing


def refresh_row_state(row: InventoryIntakeRow) -> None:
    """Recompute a row's gap flags and ready/needs-review status.

    Committed and skipped rows are left alone — their status is a record of
    what happened, not a derived value.
    """
    missing = compute_missing_fields(row)
    row.missing_fields = json.dumps(missing)
    if row.status in (IntakeRowStatus.committed, IntakeRowStatus.skipped):
        return
    row.status = IntakeRowStatus.needs_review if missing else IntakeRowStatus.ready


# --------------------------------------------------------------------------
# Building a batch from a parse result
# --------------------------------------------------------------------------

def _clean(value: object, limit: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit] if limit else text


def _parse_date(value: object) -> date | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        # A date the model couldn't normalize is treated as absent, so it
        # shows up as a gap for the reviewer rather than a silent wrong date.
        return None


def _parse_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_attributes(raw: object) -> str | None:
    """Keep only recognized product attributes, trimmed to column length."""
    if not isinstance(raw, dict):
        return None
    attributes = {}
    for field in ATTRIBUTE_FIELDS:
        value = _clean(raw.get(field), ATTRIBUTE_MAX_LENGTH)
        if value:
            attributes[field] = value
    return json.dumps(attributes) if attributes else None


def create_batch_from_parse(
    db: Session,
    parsed: dict,
    source_kind: IntakeSourceKind,
    source_name: str | None,
    raw_text: str | None,
) -> InventoryIntakeBatch:
    batch = InventoryIntakeBatch(
        source_kind=source_kind,
        source_name=_clean(source_name, NAME_MAX_LENGTH),
        raw_text=raw_text,
        parser_notes=_clean(parsed.get("parser_notes")),
        status=IntakeBatchStatus.draft,
    )
    db.add(batch)

    for index, raw_row in enumerate(parsed.get("rows") or []):
        if not isinstance(raw_row, dict):
            continue
        confidence = raw_row.get("confidence")
        row = InventoryIntakeRow(
            batch=batch,
            row_index=index,
            raw_fragment=_clean(raw_row.get("raw_fragment")),
            product_name=_clean(raw_row.get("product_name"), NAME_MAX_LENGTH),
            category_name=_clean(raw_row.get("category"), 150),
            subtype_name=_clean(raw_row.get("subtype"), 150),
            quantity=_parse_number(raw_row.get("quantity")),
            unit_type=_clean(raw_row.get("unit_type"), 30),
            unit_cost=_parse_number(raw_row.get("unit_cost")),
            vendor_name=_clean(raw_row.get("vendor_name"), NAME_MAX_LENGTH),
            location_name=_clean(raw_row.get("location_name"), NAME_MAX_LENGTH),
            received_date=_parse_date(raw_row.get("received_date")),
            sku=_clean(raw_row.get("sku"), 100),
            description=_clean(raw_row.get("description")),
            notes=_clean(raw_row.get("notes")),
            attributes_json=_row_attributes(raw_row.get("attributes")),
            confidence=(
                IntakeConfidence(confidence)
                if confidence in {c.value for c in IntakeConfidence}
                else IntakeConfidence.medium
            ),
        )
        # Tie the row to an existing product when the name is an exact match,
        # so re-importing a familiar item tops up stock instead of creating a
        # near-duplicate product.
        row.matched_product_id = _find_existing_product_id(db, row.product_name, row.category_name)
        refresh_row_state(row)
        db.add(row)

    db.commit()
    db.refresh(batch)
    return batch


def _find_existing_product_id(db: Session, name: str | None, category_name: str | None) -> uuid.UUID | None:
    if not name:
        return None
    query = db.query(Product.id).filter(
        func.lower(Product.name) == name.lower(),
        Product.status == ActiveArchivedStatus.active,
    )
    if category_name:
        query = query.join(ProductCategory, Product.category_id == ProductCategory.id).filter(
            func.lower(ProductCategory.name) == category_name.lower()
        )
    matches = query.limit(2).all()
    # Ambiguity is left for the reviewer rather than resolved by guessing.
    return matches[0][0] if len(matches) == 1 else None


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def list_batches(db: Session, limit: int = 50, offset: int = 0) -> list[InventoryIntakeBatch]:
    return (
        db.query(InventoryIntakeBatch)
        .order_by(InventoryIntakeBatch.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_batch_or_404(db: Session, batch_id: uuid.UUID) -> InventoryIntakeBatch:
    batch = db.get(InventoryIntakeBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory import not found")
    return batch


def get_row_or_404(db: Session, row_id: uuid.UUID) -> InventoryIntakeRow:
    row = db.get(InventoryIntakeRow, row_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import row not found")
    return row


def names_to_be_created(db: Session, batch: InventoryIntakeBatch) -> dict[str, list[str]]:
    """Master-data rows that committing this batch would create.

    Surfaced before commit so a typo in a parsed vendor or category name gets
    corrected instead of quietly becoming a new record.
    """
    pending = [row for row in batch.rows if row.status == IntakeRowStatus.ready]

    def unmatched(model, values: set[str]) -> list[str]:
        if not values:
            return []
        existing = {
            name.lower()
            for (name,) in db.query(model.name).filter(func.lower(model.name).in_([v.lower() for v in values]))
        }
        return sorted(value for value in values if value.lower() not in existing)

    categories = {row.category_name for row in pending if row.category_name and row.matched_product_id is None}
    vendors = {row.vendor_name for row in pending if row.vendor_name}
    locations = {row.location_name for row in pending if row.location_name}

    new_products = sorted(
        {
            row.product_name
            for row in pending
            if row.matched_product_id is None and row.product_name
        }
    )
    return {
        "categories": unmatched(ProductCategory, categories),
        "vendors": unmatched(Vendor, vendors),
        "locations": unmatched(Location, locations),
        "products": new_products,
    }


# Per-field verdicts for the name fields that resolve to master data.
MATCH_EXISTING = "existing"
MATCH_NEW = "new"
MATCH_AMBIGUOUS = "ambiguous"

NAME_MATCH_MODELS = {
    "category_name": ProductCategory,
    "vendor_name": Vendor,
    "location_name": Location,
}


def resolve_name_matches(db: Session, rows: list[InventoryIntakeRow]) -> dict[uuid.UUID, dict[str, str]]:
    """Per row, say whether each name field lines up with something on file.

    This is what lets the review screen mark the one row whose vendor is
    spelled "Fire Mtn Gems" — the batch-level `will_create` list says a new
    vendor would appear, but not which row to fix.

    Queried in bulk (a handful of statements for the whole batch, not four per
    row) so a 200-row import doesn't turn the review screen into a thousand
    round trips.
    """
    if not rows:
        return {}

    # One lookup per master-data table, covering every name in the batch.
    existing_names: dict[str, set[str]] = {}
    for field, model in NAME_MATCH_MODELS.items():
        wanted = {getattr(row, field).lower() for row in rows if getattr(row, field)}
        existing_names[field] = (
            {name.lower() for (name,) in db.query(model.name).filter(func.lower(model.name).in_(wanted))}
            if wanted
            else set()
        )

    # Products are matched by name within a category, so carry both and count
    # the candidates — two products of the same name is ambiguity the reviewer
    # has to settle, not a match.
    product_names = {row.product_name.lower() for row in rows if row.product_name}
    product_candidates: list[tuple[str, str | None]] = []
    if product_names:
        product_candidates = [
            (name.lower(), category.lower() if category else None)
            for name, category in db.query(Product.name, ProductCategory.name)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .filter(
                func.lower(Product.name).in_(product_names),
                Product.status == ActiveArchivedStatus.active,
            )
        ]

    verdicts: dict[uuid.UUID, dict[str, str]] = {}
    for row in rows:
        row_verdicts: dict[str, str] = {}

        for field in NAME_MATCH_MODELS:
            value = getattr(row, field)
            if not value:
                continue
            row_verdicts[field] = (
                MATCH_EXISTING if value.lower() in existing_names[field] else MATCH_NEW
            )

        if row.matched_product_id is not None:
            row_verdicts["product_name"] = MATCH_EXISTING
        elif row.product_name:
            candidates = [c for c in product_candidates if c[0] == row.product_name.lower()]
            if row.category_name:
                candidates = [c for c in candidates if c[1] == row.category_name.lower()]
            row_verdicts["product_name"] = MATCH_AMBIGUOUS if len(candidates) > 1 else MATCH_NEW

        verdicts[row.id] = row_verdicts

    return verdicts


# --------------------------------------------------------------------------
# Edits
# --------------------------------------------------------------------------

EDITABLE_FIELDS = {
    "product_name",
    "category_name",
    "subtype_name",
    "matched_product_id",
    "quantity",
    "unit_type",
    "unit_cost",
    "vendor_name",
    "location_name",
    "received_date",
    "sku",
    "description",
    "notes",
    "attributes_json",
}


def update_row(db: Session, row_id: uuid.UUID, changes: dict) -> InventoryIntakeRow:
    row = get_row_or_404(db, row_id)
    if row.status == IntakeRowStatus.committed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This row has already been saved to inventory and can't be edited here.",
        )

    # Checked before it's assigned: the column is a real foreign key, so a
    # bogus id would otherwise surface as a database error on commit instead
    # of a straight answer here.
    matched_id = changes.get("matched_product_id")
    if matched_id is not None and db.get(Product, matched_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That product doesn't exist. Pick one from the list, or leave it blank to create a new product.",
        )

    for field, value in changes.items():
        if field in EDITABLE_FIELDS:
            setattr(row, field, value)

    # Correcting the name or category re-runs the product match, so fixing a
    # misspelling actually lands on the existing product — and so the "new vs
    # on file" indicator reflects the corrected name rather than the parse.
    # An explicit matched_product_id in the same request wins; otherwise a
    # renamed row gives up its old auto-match, since the old one described a
    # different name.
    if "matched_product_id" not in changes and ("product_name" in changes or "category_name" in changes):
        row.matched_product_id = _find_existing_product_id(db, row.product_name, row.category_name)

    # Editing a row the reviewer had skipped brings it back into play.
    if row.status == IntakeRowStatus.skipped:
        row.status = IntakeRowStatus.needs_review
    # A hand-edited row is no longer the parser's guess.
    row.confidence = IntakeConfidence.high
    row.commit_error = None
    refresh_row_state(row)
    db.commit()
    db.refresh(row)
    return row


def bulk_update_rows(db: Session, batch_id: uuid.UUID, changes: dict) -> InventoryIntakeBatch:
    """Apply the same values to every not-yet-committed row in a batch.

    Spreadsheets routinely omit a received date, vendor or location for every
    row because it was obvious in context. Filling those in one row at a time
    would be the most tedious part of the review.
    """
    batch = get_batch_or_404(db, batch_id)
    applicable = {field: value for field, value in changes.items() if field in EDITABLE_FIELDS}
    if not applicable:
        return batch

    for row in batch.rows:
        if row.status == IntakeRowStatus.committed:
            continue
        for field, value in applicable.items():
            setattr(row, field, value)
        # Setting the category for the whole batch can bring unmatched rows
        # into range of an existing product. Rows already tied to a product
        # keep that tie — a bulk fill shouldn't undo a deliberate pick.
        if "category_name" in applicable and row.matched_product_id is None:
            row.matched_product_id = _find_existing_product_id(db, row.product_name, row.category_name)
        row.commit_error = None
        refresh_row_state(row)
    db.commit()
    db.refresh(batch)
    return batch


def set_row_skipped(db: Session, row_id: uuid.UUID, skipped: bool) -> InventoryIntakeRow:
    row = get_row_or_404(db, row_id)
    if row.status == IntakeRowStatus.committed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This row has already been saved to inventory.",
        )
    row.status = IntakeRowStatus.skipped if skipped else IntakeRowStatus.needs_review
    if not skipped:
        refresh_row_state(row)
    db.commit()
    db.refresh(row)
    return row


def delete_batch(db: Session, batch_id: uuid.UUID) -> None:
    batch = get_batch_or_404(db, batch_id)
    committed = [row for row in batch.rows if row.status == IntakeRowStatus.committed]
    if committed:
        # The inventory those rows created stays put; only the staging record
        # is marked away, so the link from stock back to its source survives.
        batch.status = IntakeBatchStatus.discarded
        db.commit()
        return
    db.delete(batch)
    db.commit()


# --------------------------------------------------------------------------
# Commit
# --------------------------------------------------------------------------

def _get_or_create_by_name(db: Session, model, name: str):
    existing = db.query(model).filter(func.lower(model.name) == name.lower()).first()
    if existing is not None:
        return existing
    # Truncate to the target column's own length, not a shared constant:
    # product_categories.name is String(100) while vendors and locations are
    # String(255), and a long parsed name would otherwise fail the insert.
    limit = model.__table__.c.name.type.length or NAME_MAX_LENGTH
    created = model(name=name[:limit])
    db.add(created)
    db.flush()
    return created


def _resolve_subtype(db: Session, category_id: uuid.UUID, name: str | None) -> tuple[uuid.UUID | None, str | None]:
    """Match a subtype within the category, or keep it as free text.

    Subtypes are scoped to a category and curated, so an unrecognized one
    becomes `custom_subtype` rather than a new shared list entry — the same
    thing the product form does when "Other" is chosen.
    """
    if not name:
        return None, None
    subtype = (
        db.query(ProductSubtype)
        .filter(ProductSubtype.category_id == category_id, func.lower(ProductSubtype.name) == name.lower())
        .first()
    )
    if subtype is not None:
        return subtype.id, None
    return None, name[:100]


def _build_product(db: Session, row: InventoryIntakeRow) -> Product:
    category = _get_or_create_by_name(db, ProductCategory, row.category_name)
    subtype_id, custom_subtype = _resolve_subtype(db, category.id, row.subtype_name)

    attributes = {}
    if row.attributes_json:
        try:
            loaded = json.loads(row.attributes_json)
            if isinstance(loaded, dict):
                attributes = {
                    field: str(value)[:ATTRIBUTE_MAX_LENGTH]
                    for field, value in loaded.items()
                    if field in ATTRIBUTE_FIELDS and value
                }
        except json.JSONDecodeError:
            # Hand-edited JSON that no longer parses shouldn't cost the row;
            # the attributes are a bonus, the inventory unit is the point.
            attributes = {}

    product = Product(
        name=row.product_name[:NAME_MAX_LENGTH],
        category_id=category.id,
        subtype_id=subtype_id,
        custom_subtype=custom_subtype,
        description=row.description,
        # The code a source lists is the *supplier's*, which is why it lands
        # in vendor_sku. The shop's own `sku` is generated here and never
        # taken from an import — so two vendors using the same code is a
        # non-event rather than a unique-constraint collision.
        vendor_sku=row.sku,
        sku=sku_service.generate_product_sku(db),
        source_type=ProductSourceType.purchased,
        **attributes,
    )
    db.add(product)
    db.flush()
    return product


def _commit_row(db: Session, row: InventoryIntakeRow) -> None:
    """Turn one ready row into real inventory. Raises on anything unworkable."""
    if row.matched_product_id is not None:
        product = db.get(Product, row.matched_product_id)
        if product is None:
            raise ValueError("The product this row was matched to no longer exists.")
    else:
        product = _build_product(db, row)
        row.created_product_id = product.id

    vendor = _get_or_create_by_name(db, Vendor, row.vendor_name) if row.vendor_name else None
    location = _get_or_create_by_name(db, Location, row.location_name) if row.location_name else None

    unit = InventoryUnit(
        product_id=product.id,
        quantity=float(row.quantity),
        unit_type=UnitType(row.unit_type),
        received_date=row.received_date,
        cost_amount=float(row.unit_cost) if row.unit_cost is not None else None,
        cost_currency="USD" if row.unit_cost is not None else None,
        vendor_id=vendor.id if vendor else None,
        location_id=location.id if location else None,
        notes=row.notes,
    )
    db.add(unit)
    db.flush()

    row.created_inventory_unit_id = unit.id
    row.status = IntakeRowStatus.committed
    row.commit_error = None


def commit_batch(db: Session, batch_id: uuid.UUID) -> dict:
    """Commit every ready row, independently.

    Each row gets its own savepoint so one bad row can't discard the rest of
    the import — it comes back with an explanation attached and stays in the
    batch for another try.
    """
    batch = get_batch_or_404(db, batch_id)

    ready = [row for row in batch.rows if row.status == IntakeRowStatus.ready]
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No rows are ready to save. Fill in the flagged fields on at least one row, "
                "or skip the rows you don't want."
            ),
        )

    errors: dict[uuid.UUID, str] = {}
    committed = 0
    for row in ready:
        savepoint = db.begin_nested()
        try:
            _commit_row(db, row)
            savepoint.commit()
            committed += 1
        except Exception as exc:  # noqa: BLE001 - recorded on the row, not swallowed
            savepoint.rollback()
            errors[row.id] = str(exc)[:500] or exc.__class__.__name__

    # Error text is written outside the savepoints so a rollback can't undo
    # the very explanation the reviewer needs.
    for row in ready:
        if row.id in errors:
            row.status = IntakeRowStatus.needs_review
            row.commit_error = errors[row.id]

    outstanding = [
        row
        for row in batch.rows
        if row.status not in (IntakeRowStatus.committed, IntakeRowStatus.skipped)
    ]
    if not outstanding:
        batch.status = IntakeBatchStatus.committed

    db.commit()
    db.refresh(batch)
    return {
        "batch_id": batch.id,
        "committed": committed,
        "failed": len(errors),
        "remaining": len(outstanding),
        "batch_status": batch.status,
    }
