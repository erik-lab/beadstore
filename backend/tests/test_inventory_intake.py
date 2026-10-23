"""Tests for staged inventory intake.

The AI pass itself is stubbed out — these tests are about everything around
it: turning files into text, flagging gaps, reviewing/editing, and the commit
that turns draft rows into real products and inventory units.
"""
import base64
import io
import json
import uuid
import zipfile
from datetime import date

import pytest

from app.models.enums import IntakeBatchStatus, IntakeRowStatus, IntakeSourceKind, UnitType
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.models.product_category import ProductCategory, ProductSubtype
from app.models.vendor import Vendor
from app.services import intake_extract, intake_parse, intake_service

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

ALL_ATTRIBUTES = {field: None for field in intake_parse.ATTRIBUTE_DESCRIPTIONS}


def parsed_row(**overrides) -> dict:
    """A parser-shaped row with every field present, as the schema requires."""
    row = {
        "product_name": "8mm Round Czech Glass",
        "category": "Beads",
        "subtype": None,
        "quantity": 5,
        "unit_type": "strand",
        "unit_cost": 3.5,
        "vendor_name": None,
        "location_name": None,
        "received_date": "2026-10-01",
        "sku": None,
        "description": None,
        "notes": None,
        "attributes": dict(ALL_ATTRIBUTES),
        "confidence": "high",
        "raw_fragment": "5 strands 8mm round Czech glass @ 3.50",
    }
    row.update(overrides)
    return row


def parse_result(rows: list[dict], parser_notes: str | None = None) -> dict:
    return {"rows": rows, "parser_notes": parser_notes}


@pytest.fixture()
def stub_parser(monkeypatch):
    """Replace the AI call with a canned result.

    Returns a setter so each test can declare what the parser 'found', and
    records the text it was handed so prompt plumbing can be asserted.
    """
    state = {"result": parse_result([]), "calls": []}

    def fake_parse_text(db, text, context_hint=""):
        state["calls"].append({"text": text, "hint": context_hint})
        return state["result"]

    def fake_parse_document(db, data_base64, mime_type, context_hint=""):
        state["calls"].append({"mime_type": mime_type, "hint": context_hint})
        return state["result"]

    monkeypatch.setattr(intake_parse, "parse_text", fake_parse_text)
    monkeypatch.setattr(intake_parse, "parse_document", fake_parse_document)
    return state


def post_text(client, auth_headers, text="some inventory", **kwargs):
    payload = {"text": text, **kwargs}
    return client.post("/api/v1/inventory-intake/parse-text", json=payload, headers=auth_headers)


# --------------------------------------------------------------------------
# File text extraction
# --------------------------------------------------------------------------

def test_extract_csv_normalizes_to_tab_separated():
    data = b"Name,Qty,Unit\n8mm round,5,strand\n\n6mm bicone,3,strand\n"
    text = intake_extract.extract_text(data, "stock.csv", "text/csv")
    assert text.splitlines() == ["Name\tQty\tUnit", "8mm round\t5\tstrand", "6mm bicone\t3\tstrand"]


def test_extract_csv_handles_semicolon_delimiter():
    data = b"Name;Qty\n8mm round;5\n"
    text = intake_extract.extract_text(data, "stock.csv", "text/csv")
    assert text.splitlines() == ["Name\tQty", "8mm round\t5"]


def test_extension_wins_over_browser_declared_mime_type():
    """Browsers often report .csv as an Excel type depending on local setup."""
    data = b"Name,Qty\n8mm round,5\n"
    text = intake_extract.extract_text(data, "stock.csv", "application/vnd.ms-excel")
    assert "8mm round\t5" in text


def test_extract_xlsx_renders_sheets():
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Beads"
    sheet.append(["Name", "Qty"])
    sheet.append(["8mm round", 5])
    buffer = io.BytesIO()
    workbook.save(buffer)

    text = intake_extract.extract_text(buffer.getvalue(), "stock.xlsx", "")
    assert "--- Sheet: Beads ---" in text
    assert "8mm round\t5" in text


def test_extract_docx_reads_paragraphs_and_tables():
    document_xml = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        "<w:p><w:r><w:t>Order from Fire Mountain</w:t></w:r></w:p>"
        "<w:p><w:r><w:t></w:t></w:r></w:p>"
        "<w:tbl><w:tr>"
        "<w:tc><w:p><w:r><w:t>8mm round</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>5</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
        "</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    text = intake_extract.extract_text(buffer.getvalue(), "order.docx", "")
    assert text.splitlines() == ["Order from Fire Mountain", "8mm round\t5"]


def test_extract_html_strips_markup():
    data = b"<html><body><p>8mm round</p><script>bad()</script><p>5 strands</p></body></html>"
    text = intake_extract.extract_text(data, "note.html", "")
    assert "bad()" not in text
    assert "8mm round" in text and "5 strands" in text


def test_extract_rejects_unsupported_type():
    with pytest.raises(Exception) as exc:
        intake_extract.extract_text(b"\x00\x01", "thing.dwg", "application/acad")
    assert exc.value.status_code == 400
    assert "paste" in exc.value.detail.lower()


def test_extract_rejects_empty_text():
    with pytest.raises(Exception) as exc:
        intake_extract.extract_text(b"   \n  ", "blank.txt", "text/plain")
    assert exc.value.status_code == 400


def test_extract_rejects_oversized_text():
    data = b"x" * (intake_extract.MAX_EXTRACTED_CHARS + 10)
    with pytest.raises(Exception) as exc:
        intake_extract.extract_text(data, "huge.txt", "text/plain")
    assert exc.value.status_code == 413


def test_extract_rejects_damaged_office_file():
    with pytest.raises(Exception) as exc:
        intake_extract.extract_text(b"not a zip at all", "order.docx", "")
    assert exc.value.status_code == 400


# --------------------------------------------------------------------------
# Gap detection
# --------------------------------------------------------------------------

def test_parse_flags_every_missing_required_field(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result(
        [parsed_row(category=None, quantity=None, unit_type=None, received_date=None)]
    )
    response = post_text(client, auth_headers)
    assert response.status_code == 201

    row = response.json()["rows"][0]
    assert set(row["missing_fields"]) == {"category_name", "quantity", "unit_type", "received_date"}
    assert row["status"] == "needs_review"


def test_complete_row_is_ready_with_no_gaps(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["missing_fields"] == []
    assert row["status"] == "ready"


def test_unparseable_date_is_treated_as_missing(client, auth_headers, stub_parser):
    """A date the model couldn't normalize becomes a gap, not a wrong date."""
    stub_parser["result"] = parse_result([parsed_row(received_date="sometime last spring")])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["received_date"] is None
    assert "received_date" in row["missing_fields"]


def test_invalid_unit_type_survives_for_review_but_blocks_commit(client, auth_headers, stub_parser):
    """A bad guess is kept visible rather than dropped, and flagged as a gap."""
    stub_parser["result"] = parse_result([parsed_row(unit_type="hank")])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["unit_type"] == "hank"
    assert "unit_type" in row["missing_fields"]
    assert row["status"] == "needs_review"


def test_zero_quantity_counts_as_missing(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row(quantity=0)])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert "quantity" in row["missing_fields"]


def test_parser_notes_and_fragment_are_kept(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()], parser_notes="Prices looked like line totals.")
    body = post_text(client, auth_headers).json()
    assert body["parser_notes"] == "Prices looked like line totals."
    assert body["rows"][0]["raw_fragment"].startswith("5 strands")


def test_attributes_round_trip_as_an_object(client, auth_headers, stub_parser):
    attributes = dict(ALL_ATTRIBUTES, material="Czech glass", size="8mm", shape="round")
    stub_parser["result"] = parse_result([parsed_row(attributes=attributes)])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["attributes"] == {"material": "Czech glass", "size": "8mm", "shape": "round"}


def test_overlong_attribute_values_are_truncated(client, auth_headers, stub_parser):
    """Attribute columns are String(100); a verbose source shouldn't fail the row."""
    attributes = dict(ALL_ATTRIBUTES, material="x" * 300)
    stub_parser["result"] = parse_result([parsed_row(attributes=attributes)])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert len(row["attributes"]["material"]) == intake_service.ATTRIBUTE_MAX_LENGTH


def test_unknown_attribute_keys_are_dropped(client, auth_headers, stub_parser):
    attributes = dict(ALL_ATTRIBUTES, material="Czech glass", vibe="cheerful")
    stub_parser["result"] = parse_result([parsed_row(attributes=attributes)])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["attributes"] == {"material": "Czech glass"}


def test_rows_beyond_the_cap_are_dropped_with_a_note(client, auth_headers, monkeypatch):
    """Guards against one enormous source producing an unreviewable batch."""
    monkeypatch.setattr(intake_parse, "MAX_ROWS", 2)
    monkeypatch.setattr(intake_parse.settings, "anthropic_api_key", "test-key", raising=False)

    class FakeBlock:
        type = "text"
        text = json.dumps(parse_result([parsed_row() for _ in range(5)]))

    class FakeResponse:
        stop_reason = "end_turn"
        content = [FakeBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr(intake_parse.anthropic, "Anthropic", FakeClient)

    body = post_text(client, auth_headers).json()
    assert len(body["rows"]) == 2
    assert "first 2 items" in body["parser_notes"]


# --------------------------------------------------------------------------
# Review and editing
# --------------------------------------------------------------------------

def test_editing_a_row_clears_its_gap_and_makes_it_ready(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row(quantity=None)])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["status"] == "needs_review"

    response = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}", json={"quantity": 4}, headers=auth_headers
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["quantity"] == 4
    assert updated["missing_fields"] == []
    assert updated["status"] == "ready"
    # A hand-checked value is no longer the parser's guess.
    assert updated["confidence"] == "high"


def test_editing_can_reintroduce_a_gap(client, auth_headers, stub_parser):
    """Gap flags are recomputed on every write, not only at parse time."""
    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]

    updated = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}", json={"unit_type": None}, headers=auth_headers
    ).json()
    assert "unit_type" in updated["missing_fields"]
    assert updated["status"] == "needs_review"


def test_client_cannot_fake_a_rows_missing_fields(client, auth_headers, stub_parser):
    """missing_fields is derived server-side — a client can't declare a row clean."""
    stub_parser["result"] = parse_result([parsed_row(quantity=None)])
    row = post_text(client, auth_headers).json()["rows"][0]

    updated = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}",
        json={"missing_fields": [], "status": "ready"},
        headers=auth_headers,
    ).json()
    assert updated["missing_fields"] == ["quantity"]
    assert updated["status"] == "needs_review"


def test_bulk_update_fills_a_shared_value_across_rows(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result(
        [parsed_row(received_date=None), parsed_row(product_name="6mm bicone", received_date=None)]
    )
    batch = post_text(client, auth_headers).json()
    assert all("received_date" in row["missing_fields"] for row in batch["rows"])

    response = client.patch(
        f"/api/v1/inventory-intake/batches/{batch['id']}/rows",
        json={"received_date": "2026-10-15", "vendor_name": "Fire Mountain Gems"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert all(row["received_date"] == "2026-10-15" for row in rows)
    assert all(row["vendor_name"] == "Fire Mountain Gems" for row in rows)
    assert all(row["status"] == "ready" for row in rows)


def test_skipping_a_row_excludes_it_then_unskipping_restores_it(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]

    skipped = client.post(
        f"/api/v1/inventory-intake/rows/{row['id']}/skip", json={"skipped": True}, headers=auth_headers
    ).json()
    assert skipped["status"] == "skipped"

    restored = client.post(
        f"/api/v1/inventory-intake/rows/{row['id']}/skip", json={"skipped": False}, headers=auth_headers
    ).json()
    assert restored["status"] == "ready"


def test_each_name_field_says_whether_it_is_on_file(client, auth_headers, stub_parser, db_session):
    """The batch-level list says a new vendor would appear; this says which row."""
    category = ProductCategory(name="Beads")
    db_session.add_all([category, Vendor(name="Fire Mountain Gems")])
    db_session.commit()

    stub_parser["result"] = parse_result(
        [
            parsed_row(vendor_name="fire mountain gems", location_name="Bin 4"),
            parsed_row(product_name="6mm Bicone", category="Pendants", vendor_name="Fire Mtn Gems"),
        ]
    )
    rows = post_text(client, auth_headers).json()["rows"]

    assert rows[0]["name_matches"]["category_name"] == "existing"
    # Matched case-insensitively against the vendor already on file.
    assert rows[0]["name_matches"]["vendor_name"] == "existing"
    assert rows[0]["name_matches"]["location_name"] == "new"
    assert rows[0]["name_matches"]["product_name"] == "new"

    # The misspelled vendor and the unknown category are flagged on their row.
    assert rows[1]["name_matches"]["vendor_name"] == "new"
    assert rows[1]["name_matches"]["category_name"] == "new"


def test_blank_name_fields_get_no_verdict(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row(vendor_name=None, location_name=None)])
    matches = post_text(client, auth_headers).json()["rows"][0]["name_matches"]
    assert "vendor_name" not in matches
    assert "location_name" not in matches


def test_a_name_matching_two_products_reads_as_ambiguous(client, auth_headers, stub_parser, db_session):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    db_session.add_all(
        [
            Product(name="8mm Round Czech Glass", category_id=category.id),
            Product(name="8mm round czech glass", category_id=category.id),
        ]
    )
    db_session.commit()

    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["matched_product_id"] is None
    assert row["name_matches"]["product_name"] == "ambiguous"


def test_an_archived_product_does_not_count_as_on_file(client, auth_headers, stub_parser, db_session):
    from app.models.enums import ActiveArchivedStatus

    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    db_session.add(
        Product(
            name="8mm Round Czech Glass",
            category_id=category.id,
            status=ActiveArchivedStatus.archived,
        )
    )
    db_session.commit()

    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["name_matches"]["product_name"] == "new"


def test_correcting_a_name_rematches_and_updates_the_verdict(
    client, auth_headers, stub_parser, db_session
):
    """Fixing a misspelling has to land on the existing product, not just
    change the text — otherwise the indicator would keep saying 'new'."""
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    existing = Product(name="8mm Round Czech Glass", category_id=category.id)
    db_session.add(existing)
    db_session.commit()
    existing_id = existing.id

    stub_parser["result"] = parse_result([parsed_row(product_name="8mm Rnd Czech Gls")])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["matched_product_id"] is None
    assert row["name_matches"]["product_name"] == "new"

    corrected = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}",
        json={"product_name": "8mm Round Czech Glass"},
        headers=auth_headers,
    ).json()
    assert corrected["matched_product_id"] == str(existing_id)
    assert corrected["name_matches"]["product_name"] == "existing"


def test_correcting_a_vendor_spelling_updates_its_verdict(
    client, auth_headers, stub_parser, db_session
):
    db_session.add(Vendor(name="Fire Mountain Gems"))
    db_session.commit()

    stub_parser["result"] = parse_result([parsed_row(vendor_name="Fire Mtn Gems")])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["name_matches"]["vendor_name"] == "new"

    corrected = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}",
        json={"vendor_name": "Fire Mountain Gems"},
        headers=auth_headers,
    ).json()
    assert corrected["name_matches"]["vendor_name"] == "existing"


def test_renaming_a_row_gives_up_a_stale_auto_match(client, auth_headers, stub_parser, db_session):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    db_session.add(Product(name="8mm Round Czech Glass", category_id=category.id))
    db_session.commit()

    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["matched_product_id"] is not None

    renamed = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}",
        json={"product_name": "Something else entirely"},
        headers=auth_headers,
    ).json()
    assert renamed["matched_product_id"] is None
    assert renamed["name_matches"]["product_name"] == "new"


def test_an_explicit_product_pick_survives_an_edit_in_the_same_request(
    client, auth_headers, stub_parser, db_session
):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    chosen = Product(name="Totally different name", category_id=category.id)
    db_session.add(chosen)
    db_session.commit()
    chosen_id = chosen.id

    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]

    updated = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}",
        json={"product_name": "8mm Round Czech Glass", "matched_product_id": str(chosen_id)},
        headers=auth_headers,
    ).json()
    assert updated["matched_product_id"] == str(chosen_id)


def test_bulk_category_fill_can_bring_rows_into_range_of_a_product(
    client, auth_headers, stub_parser, db_session
):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    existing = Product(name="8mm Round Czech Glass", category_id=category.id)
    db_session.add(existing)
    db_session.commit()
    existing_id = existing.id

    # No category from the source, so the name alone can't be scoped.
    stub_parser["result"] = parse_result([parsed_row(category=None)])
    batch = post_text(client, auth_headers).json()

    rows = client.patch(
        f"/api/v1/inventory-intake/batches/{batch['id']}/rows",
        json={"category_name": "Beads"},
        headers=auth_headers,
    ).json()["rows"]
    assert rows[0]["matched_product_id"] == str(existing_id)
    assert rows[0]["name_matches"]["product_name"] == "existing"


def test_will_create_lists_master_data_a_commit_would_add(client, auth_headers, stub_parser, db_session):
    db_session.add(Vendor(name="Fire Mountain Gems"))
    db_session.commit()

    stub_parser["result"] = parse_result(
        [parsed_row(vendor_name="fire mountain gems", location_name="Bin 4")]
    )
    batch = post_text(client, auth_headers).json()

    assert batch["will_create"]["categories"] == ["Beads"]
    assert batch["will_create"]["locations"] == ["Bin 4"]
    # Matched case-insensitively against the existing vendor, so nothing new.
    assert batch["will_create"]["vendors"] == []
    assert batch["will_create"]["products"] == ["8mm Round Czech Glass"]


# --------------------------------------------------------------------------
# Commit
# --------------------------------------------------------------------------

def test_commit_creates_product_and_inventory_unit(client, auth_headers, stub_parser, db_session):
    attributes = dict(ALL_ATTRIBUTES, material="Czech glass", size="8mm", shape="round")
    stub_parser["result"] = parse_result(
        [parsed_row(attributes=attributes, vendor_name="Fire Mountain Gems", location_name="Bin 4")]
    )
    batch = post_text(client, auth_headers).json()

    response = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch["id"],
        "committed": 1,
        "failed": 0,
        "remaining": 0,
        "batch_status": "committed",
    }

    product = db_session.query(Product).one()
    assert product.name == "8mm Round Czech Glass"
    assert product.material == "Czech glass"
    assert product.size == "8mm"
    assert product.category.name == "Beads"

    unit = db_session.query(InventoryUnit).one()
    assert unit.product_id == product.id
    assert float(unit.quantity) == 5
    assert unit.unit_type == UnitType.strand
    assert unit.received_date == date(2026, 10, 1)
    assert float(unit.cost_amount) == 3.5
    assert unit.cost_currency == "USD"
    assert unit.vendor.name == "Fire Mountain Gems"
    assert unit.location.name == "Bin 4"


def test_commit_marks_rows_with_what_they_created(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()])
    batch = post_text(client, auth_headers).json()
    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)

    row = client.get(f"/api/v1/inventory-intake/batches/{batch['id']}", headers=auth_headers).json()["rows"][0]
    assert row["status"] == "committed"
    assert row["created_product_id"] is not None
    assert row["created_inventory_unit_id"] is not None


def test_commit_refuses_when_nothing_is_ready(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row(quantity=None)])
    batch = post_text(client, auth_headers).json()

    response = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    )
    assert response.status_code == 400
    assert "flagged" in response.json()["detail"]


def test_commit_leaves_rows_that_still_need_review(client, auth_headers, stub_parser, db_session):
    stub_parser["result"] = parse_result([parsed_row(), parsed_row(product_name="6mm bicone", quantity=None)])
    batch = post_text(client, auth_headers).json()

    result = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    ).json()
    assert result["committed"] == 1
    assert result["remaining"] == 1
    # The batch stays open while a row still needs attention.
    assert result["batch_status"] == "draft"
    assert db_session.query(InventoryUnit).count() == 1


def test_commit_skips_skipped_rows(client, auth_headers, stub_parser, db_session):
    stub_parser["result"] = parse_result([parsed_row(), parsed_row(product_name="6mm bicone")])
    batch = post_text(client, auth_headers).json()
    client.post(
        f"/api/v1/inventory-intake/rows/{batch['rows'][1]['id']}/skip",
        json={"skipped": True},
        headers=auth_headers,
    )

    result = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    ).json()
    assert result["committed"] == 1
    # Skipped rows are a decision, not outstanding work, so the batch closes.
    assert result["batch_status"] == "committed"
    assert db_session.query(Product).count() == 1


def test_commit_adds_stock_to_an_existing_product_instead_of_duplicating(
    client, auth_headers, stub_parser, db_session
):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    existing = Product(name="8mm Round Czech Glass", category_id=category.id)
    db_session.add(existing)
    db_session.commit()
    existing_id = existing.id

    stub_parser["result"] = parse_result([parsed_row()])
    batch = post_text(client, auth_headers).json()
    assert batch["rows"][0]["matched_product_id"] == str(existing_id)

    # The review screen names the product rather than showing a bare ID.
    assert batch["rows"][0]["matched_product_name"] == "8mm Round Czech Glass"

    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)

    assert db_session.query(Product).count() == 1
    unit = db_session.query(InventoryUnit).one()
    assert unit.product_id == existing_id


def test_ambiguous_product_name_is_left_for_the_reviewer(client, auth_headers, stub_parser, db_session):
    """Two products with the same name shouldn't be resolved by guessing."""
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    db_session.add_all(
        [
            Product(name="8mm Round Czech Glass", category_id=category.id),
            Product(name="8mm round czech glass", category_id=category.id),
        ]
    )
    db_session.commit()

    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]
    assert row["matched_product_id"] is None


def test_commit_reuses_a_category_created_earlier_in_the_same_batch(
    client, auth_headers, stub_parser, db_session
):
    stub_parser["result"] = parse_result(
        [parsed_row(), parsed_row(product_name="6mm Bicone"), parsed_row(product_name="4mm Seed")]
    )
    batch = post_text(client, auth_headers).json()
    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)

    assert db_session.query(ProductCategory).filter_by(name="Beads").count() == 1
    assert db_session.query(Product).count() == 3


def test_commit_matches_a_known_subtype_and_keeps_unknown_ones_as_text(
    client, auth_headers, stub_parser, db_session
):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    db_session.add(ProductSubtype(category_id=category.id, name="Fire Polished"))
    db_session.commit()

    stub_parser["result"] = parse_result(
        [
            parsed_row(product_name="Known subtype", subtype="fire polished"),
            parsed_row(product_name="Novel subtype", subtype="Hand Wound"),
        ]
    )
    batch = post_text(client, auth_headers).json()
    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)

    known = db_session.query(Product).filter_by(name="Known subtype").one()
    assert known.subtype is not None and known.subtype.name == "Fire Polished"
    assert known.custom_subtype is None

    novel = db_session.query(Product).filter_by(name="Novel subtype").one()
    assert novel.subtype_id is None
    assert novel.custom_subtype == "Hand Wound"


def test_long_names_are_trimmed_to_what_each_column_holds(
    client, auth_headers, stub_parser, db_session
):
    """product_categories.name is String(100) where vendors/locations are 255."""
    stub_parser["result"] = parse_result(
        [parsed_row(category="C" * 200, vendor_name="V" * 400, location_name="L" * 400)]
    )
    batch = post_text(client, auth_headers).json()
    result = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    ).json()

    assert result["committed"] == 1
    assert len(db_session.query(ProductCategory).one().name) == 100
    assert len(db_session.query(Vendor).one().name) == 255


def test_commit_drops_a_sku_already_in_use_rather_than_failing_the_row(
    client, auth_headers, stub_parser, db_session
):
    """SKUs are unique; a collision should cost the code, not the stock."""
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    db_session.add(Product(name="Something else", category_id=category.id, sku="FMG-123"))
    db_session.commit()

    stub_parser["result"] = parse_result([parsed_row(sku="FMG-123")])
    batch = post_text(client, auth_headers).json()
    result = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    ).json()

    assert result["committed"] == 1
    created = db_session.query(Product).filter_by(name="8mm Round Czech Glass").one()
    assert created.sku is None
    assert db_session.query(InventoryUnit).count() == 1


def test_pointing_a_row_at_a_nonexistent_product_is_rejected(client, auth_headers, stub_parser):
    """matched_product_id is a real FK, so a bogus id gets a straight answer."""
    stub_parser["result"] = parse_result([parsed_row()])
    row = post_text(client, auth_headers).json()["rows"][0]

    response = client.patch(
        f"/api/v1/inventory-intake/rows/{row['id']}",
        json={"matched_product_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "doesn't exist" in response.json()["detail"]


def test_one_bad_row_does_not_discard_the_rest_of_the_batch(
    client, auth_headers, stub_parser, db_session
):
    """A failing row is isolated by its own savepoint.

    The trigger here is a product vanishing between parse and commit, which
    Postgres's foreign key would normally prevent — it exercises the
    defensive branch and, more to the point, proves the savepoint isolation.
    """
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()
    doomed = Product(name="6mm Bicone", category_id=category.id)
    db_session.add(doomed)
    db_session.commit()

    stub_parser["result"] = parse_result([parsed_row(), parsed_row(product_name="6mm Bicone")])
    batch = post_text(client, auth_headers).json()
    assert batch["rows"][1]["matched_product_id"] == str(doomed.id)

    db_session.delete(doomed)
    db_session.commit()

    result = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    ).json()
    assert result["committed"] == 1
    assert result["failed"] == 1

    rows = client.get(f"/api/v1/inventory-intake/batches/{batch['id']}", headers=auth_headers).json()["rows"]
    failed = next(row for row in rows if row["product_name"] == "6mm Bicone")
    assert failed["status"] == "needs_review"
    assert failed["commit_error"]
    # The good row's inventory survived the other row's failure.
    assert db_session.query(InventoryUnit).count() == 1


def test_a_committed_row_cannot_be_edited_or_recommitted(client, auth_headers, stub_parser, db_session):
    stub_parser["result"] = parse_result([parsed_row()])
    batch = post_text(client, auth_headers).json()
    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)
    row_id = batch["rows"][0]["id"]

    edit = client.patch(
        f"/api/v1/inventory-intake/rows/{row_id}", json={"quantity": 99}, headers=auth_headers
    )
    assert edit.status_code == 409

    recommit = client.post(
        f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers
    )
    assert recommit.status_code == 400
    # No second inventory unit from the same row.
    assert db_session.query(InventoryUnit).count() == 1


def test_bulk_update_leaves_committed_rows_alone(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row(), parsed_row(product_name="6mm Bicone", quantity=None)])
    batch = post_text(client, auth_headers).json()
    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)

    rows = client.patch(
        f"/api/v1/inventory-intake/batches/{batch['id']}/rows",
        json={"received_date": "2026-11-01"},
        headers=auth_headers,
    ).json()["rows"]

    committed = next(row for row in rows if row["status"] == "committed")
    open_row = next(row for row in rows if row["status"] != "committed")
    assert committed["received_date"] == "2026-10-01"
    assert open_row["received_date"] == "2026-11-01"


def test_staging_churn_stays_out_of_the_audit_log(client, auth_headers, stub_parser, db_session):
    """Only what a commit creates is audited — not the draft rows and edits."""
    from app.models.audit_log import AuditLog

    stub_parser["result"] = parse_result([parsed_row(), parsed_row(product_name="6mm Bicone")])
    batch = post_text(client, auth_headers).json()
    client.patch(
        f"/api/v1/inventory-intake/rows/{batch['rows'][0]['id']}",
        json={"quantity": 9},
        headers=auth_headers,
    )

    staged = db_session.query(AuditLog).filter(
        AuditLog.table_name.in_(["inventory_intake_batches", "inventory_intake_rows"])
    )
    assert staged.count() == 0

    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)

    assert db_session.query(AuditLog).filter_by(table_name="products").count() == 2
    assert db_session.query(AuditLog).filter_by(table_name="inventory_units").count() == 2
    assert staged.count() == 0


def test_intake_rows_still_record_who_created_them(client, auth_headers, stub_parser, db_session):
    """Opting out of the trail keeps the created_by stamping."""
    from app.models.inventory_intake import InventoryIntakeRow

    stub_parser["result"] = parse_result([parsed_row()])
    post_text(client, auth_headers)

    row = db_session.query(InventoryIntakeRow).one()
    assert row.created_by is not None


# --------------------------------------------------------------------------
# Batch lifecycle
# --------------------------------------------------------------------------

def test_discarding_an_untouched_batch_deletes_it(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()])
    batch = post_text(client, auth_headers).json()

    assert client.delete(f"/api/v1/inventory-intake/batches/{batch['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/inventory-intake/batches/{batch['id']}", headers=auth_headers).status_code == 404


def test_discarding_a_partly_committed_batch_keeps_the_record(
    client, auth_headers, stub_parser, db_session
):
    """The link from committed stock back to its source has to survive."""
    stub_parser["result"] = parse_result([parsed_row(), parsed_row(product_name="6mm Bicone", quantity=None)])
    batch = post_text(client, auth_headers).json()
    client.post(f"/api/v1/inventory-intake/batches/{batch['id']}/commit", headers=auth_headers)

    client.delete(f"/api/v1/inventory-intake/batches/{batch['id']}", headers=auth_headers)

    response = client.get(f"/api/v1/inventory-intake/batches/{batch['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "discarded"
    assert db_session.query(InventoryUnit).count() == 1


def test_batches_are_listed_newest_first(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()])
    post_text(client, auth_headers, source_name="First")
    post_text(client, auth_headers, source_name="Second")

    names = [batch["source_name"] for batch in client.get(
        "/api/v1/inventory-intake/batches", headers=auth_headers
    ).json()]
    assert names[:2] == ["Second", "First"]


# --------------------------------------------------------------------------
# Source kinds
# --------------------------------------------------------------------------

def test_dictation_goes_through_the_same_parser_with_a_speech_hint(client, auth_headers, stub_parser):
    """Voice is a label on the same code path, not a separate pipeline."""
    stub_parser["result"] = parse_result([parsed_row()])
    response = post_text(client, auth_headers, text="five strands of 8mm round czech glass", source_kind="voice")

    assert response.status_code == 201
    body = response.json()
    assert body["source_kind"] == "voice"
    assert body["source_name"] == "Dictated note"
    # Same parse_text call as any pasted note, with dictation context added.
    assert "dictated" in stub_parser["calls"][0]["hint"].lower()
    assert stub_parser["calls"][0]["text"] == "five strands of 8mm round czech glass"


def test_text_endpoint_rejects_a_file_source_kind(client, auth_headers, stub_parser):
    response = post_text(client, auth_headers, source_kind="spreadsheet")
    assert response.status_code == 422


def test_text_endpoint_rejects_empty_text(client, auth_headers, stub_parser):
    assert post_text(client, auth_headers, text="").status_code == 422


def test_uploaded_spreadsheet_is_extracted_then_parsed(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()])
    csv_bytes = b"Name,Qty,Unit\n8mm round,5,strand\n"

    response = client.post(
        "/api/v1/inventory-intake/parse-file",
        json={
            "filename": "stock.csv",
            "mime_type": "text/csv",
            "data_base64": base64.b64encode(csv_bytes).decode(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source_kind"] == "spreadsheet"
    assert body["source_name"] == "stock.csv"
    # The extracted text is kept so the batch can be re-read or re-parsed.
    assert "8mm round\t5\tstrand" in body["raw_text"]
    assert "8mm round\t5\tstrand" in stub_parser["calls"][0]["text"]


def test_uploaded_pdf_goes_to_the_model_natively(client, auth_headers, stub_parser):
    """Scanned invoices read better as a document block than as extracted text."""
    stub_parser["result"] = parse_result([parsed_row()])
    response = client.post(
        "/api/v1/inventory-intake/parse-file",
        json={
            "filename": "invoice.pdf",
            "mime_type": "application/pdf",
            "data_base64": base64.b64encode(b"%PDF-1.4 fake").decode(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["source_kind"] == "document"
    assert stub_parser["calls"][0]["mime_type"] == "application/pdf"


def test_uploaded_photo_goes_to_the_model_natively(client, auth_headers, stub_parser):
    stub_parser["result"] = parse_result([parsed_row()])
    response = client.post(
        "/api/v1/inventory-intake/parse-file",
        json={
            "filename": "packing-slip.jpg",
            "mime_type": "image/jpeg",
            "data_base64": base64.b64encode(b"\xff\xd8\xff fake").decode(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert stub_parser["calls"][0]["mime_type"] == "image/jpeg"


def test_malformed_base64_upload_is_rejected(client, auth_headers, stub_parser):
    response = client.post(
        "/api/v1/inventory-intake/parse-file",
        json={"filename": "stock.csv", "mime_type": "text/csv", "data_base64": "not!base64!"},
        headers=auth_headers,
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Parser prompt construction
# --------------------------------------------------------------------------

def test_prompt_is_primed_with_the_shops_own_vocabulary(db_session):
    """The parser is shown real categories/vendors so it reuses house wording."""
    from app.models.attribute_option import AttributeOption

    db_session.add_all(
        [
            ProductCategory(name="Beads"),
            Vendor(name="Fire Mountain Gems"),
            AttributeOption(field="shape", value="rondelle"),
        ]
    )
    db_session.commit()

    block = intake_parse._vocabulary_block(db_session)
    assert "Beads" in block
    assert "Fire Mountain Gems" in block
    assert "rondelle" in block


def test_vocabulary_block_handles_an_empty_shop(db_session):
    block = intake_parse._vocabulary_block(db_session)
    assert "no categories" in block


def test_attributes_schema_tracks_the_product_model():
    """Adding a product attribute column shouldn't leave the parser unable to fill it."""
    from app.services.product_service import ATTRIBUTE_FIELDS

    schema = intake_parse._attributes_schema()
    assert set(schema["properties"]) == set(ATTRIBUTE_FIELDS)
    assert set(schema["required"]) == set(ATTRIBUTE_FIELDS)


def test_parser_is_held_to_the_units_the_review_screen_offers():
    """`lot` is a real UnitType but isn't in the UI dropdown, so the parser
    mustn't emit it — a ready row with an unselectable unit reads as a bug."""
    schema = intake_parse._row_schema()
    allowed = set(schema["properties"]["unit_type"]["enum"])
    assert allowed == ({unit.value for unit in UnitType} - {"lot"}) | {None}


def test_parse_without_an_api_key_reports_it_clearly(client, auth_headers, monkeypatch):
    monkeypatch.setattr(intake_parse.settings, "anthropic_api_key", "", raising=False)
    response = post_text(client, auth_headers)
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/inventory-intake/parse-text"),
        ("post", "/api/v1/inventory-intake/parse-file"),
        ("get", "/api/v1/inventory-intake/batches"),
        ("get", f"/api/v1/inventory-intake/batches/{uuid.uuid4()}"),
        ("post", f"/api/v1/inventory-intake/batches/{uuid.uuid4()}/commit"),
        ("patch", f"/api/v1/inventory-intake/rows/{uuid.uuid4()}"),
    ],
)
def test_intake_endpoints_require_authentication(client, method, path):
    kwargs = {} if method == "get" else {"json": {}}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code in (401, 403)


def test_unknown_batch_and_row_ids_are_404(client, auth_headers):
    assert client.get(
        f"/api/v1/inventory-intake/batches/{uuid.uuid4()}", headers=auth_headers
    ).status_code == 404
    assert client.patch(
        f"/api/v1/inventory-intake/rows/{uuid.uuid4()}", json={"quantity": 1}, headers=auth_headers
    ).status_code == 404
