"""Tests for the shop's own product codes.

Bead supplies have no universal identifier, so the shop mints its own. These
codes end up on bin labels, in Code128 barcodes and on Etsy listings, so what
matters is that they're unique, stable, and survive being read by a human.
"""
import uuid

import pytest

from app.models.product import Product
from app.models.product_category import ProductCategory
from app.services import sku_service


def test_generated_codes_are_well_formed(db_session):
    sku = sku_service.generate_product_sku(db_session)
    assert sku.startswith("BS-")
    assert len(sku) == len("BS-") + sku_service.BODY_LENGTH + 1
    assert sku_service.is_valid_sku(sku)


def test_codes_avoid_the_characters_people_misread():
    """Crockford base32 drops I, L, O and U so a code can be read aloud."""
    for char in "ILOU":
        assert char not in sku_service.ALPHABET
    # And the digits they'd be confused with are present, unambiguously.
    for char in "01":
        assert char in sku_service.ALPHABET


def test_check_character_catches_transposed_characters():
    """The positional weighting exists for this — a flat sum would miss it.

    One class slips through, and it's documented in `_check_character`: two
    adjacent characters whose alphabet positions differ by exactly 16, since
    consecutive odd weights differ by 2 and the arithmetic is mod 32. Skipped
    here rather than quietly passing, so the gap stays visible.
    """
    missed = 0
    for body in ("7K3QZ", "ABCDE", "10234", "ZYXWV", "0G1H2"):
        sku = sku_service.format_sku(body)
        for index in range(len(body) - 1):
            if body[index] == body[index + 1]:
                continue
            swapped = body[:index] + body[index + 1] + body[index] + body[index + 2 :]
            candidate = "BS-" + swapped + sku[-1]
            gap = abs(sku_service.ALPHABET.index(body[index]) - sku_service.ALPHABET.index(body[index + 1]))
            if gap == 16:
                missed += 1
                continue
            assert not sku_service.is_valid_sku(candidate), f"{candidate} should fail"

    # "0G" is in the sample precisely to exercise the known gap.
    assert missed > 0, "expected the documented 16-apart case to be present in the sample"


def test_every_single_character_substitution_is_caught():
    """Exhaustive, because this is the error the check character exists for.

    Mod 32 is a power of two, so an even positional weight can be cancelled
    out by a substitution exactly 16 places away in the alphabet. Odd weights
    avoid that, and this proves it rather than trusting the reasoning.
    """
    for body in ("7K3QZ", "00000", "ZZZZZ", "0G1H2", "ABCDE"):
        sku = sku_service.format_sku(body)
        for index in range(len(body)):
            for replacement in sku_service.ALPHABET:
                if replacement == body[index]:
                    continue
                typo = "BS-" + body[:index] + replacement + body[index + 1 :] + sku[-1]
                assert not sku_service.is_valid_sku(typo), f"{typo} should fail its check"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "BS-",
        "7K3QZ4",  # no prefix
        "XX-7K3QZ4",  # wrong prefix
        "BS-7K3QZ",  # too short
        "BS-7K3QZ44",  # too long
        "BS-7K3QI4",  # I isn't in the alphabet
        "bs-7k3qz4",  # lowercase
    ],
)
def test_malformed_codes_are_rejected(bad):
    assert not sku_service.is_valid_sku(bad)


def test_generation_skips_a_code_already_taken(db_session, monkeypatch):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.flush()

    taken = sku_service.format_sku("AAAAA")
    db_session.add(Product(name="Already here", category_id=category.id, sku=taken))
    db_session.commit()

    # The generator draws one character at a time, so feeding it a fixed
    # sequence makes the first body collide and the second be free.
    draws = iter("AAAAA" + "BBBBB")
    monkeypatch.setattr(sku_service.secrets, "choice", lambda alphabet: next(draws))

    assert sku_service.generate_product_sku(db_session) == sku_service.format_sku("BBBBB")


def test_creating_a_product_assigns_a_code(client, auth_headers, db_session):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.commit()

    resp = client.post(
        "/api/v1/products",
        json={"name": "8mm Round Czech Glass", "category_id": str(category.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    sku = resp.json()["sku"]
    assert sku_service.is_valid_sku(sku)


def test_codes_are_unique_across_many_products(client, auth_headers, db_session):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.commit()

    skus = set()
    for index in range(25):
        resp = client.post(
            "/api/v1/products",
            json={"name": f"Product {index}", "category_id": str(category.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        skus.add(resp.json()["sku"])
    assert len(skus) == 25


def test_a_client_cannot_set_or_change_the_shop_code(client, auth_headers, db_session):
    """The code goes on a printed label and onto Etsy — it can't be editable."""
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.commit()

    created = client.post(
        "/api/v1/products",
        json={
            "name": "Tries to pick its own",
            "category_id": str(category.id),
            "sku": "BS-ZZZZZ0",
        },
        headers=auth_headers,
    ).json()
    assert created["sku"] != "BS-ZZZZZ0"
    assigned = created["sku"]

    updated = client.patch(
        f"/api/v1/products/{created['id']}",
        json={"sku": "BS-ZZZZZ0"},
        headers=auth_headers,
    ).json()
    assert updated["sku"] == assigned


def test_vendor_code_is_separate_and_editable(client, auth_headers, db_session):
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.commit()

    created = client.post(
        "/api/v1/products",
        json={
            "name": "Has a supplier code",
            "category_id": str(category.id),
            "vendor_sku": "FMG-123",
        },
        headers=auth_headers,
    ).json()
    assert created["vendor_sku"] == "FMG-123"
    assert created["sku"] != "FMG-123"

    updated = client.patch(
        f"/api/v1/products/{created['id']}",
        json={"vendor_sku": "FMG-456"},
        headers=auth_headers,
    ).json()
    assert updated["vendor_sku"] == "FMG-456"


def test_two_products_can_share_a_vendor_code(client, auth_headers, db_session):
    """Vendors reuse each other's codes, so vendor_sku must not be unique."""
    category = ProductCategory(name="Beads")
    db_session.add(category)
    db_session.commit()

    for name in ("First", "Second"):
        resp = client.post(
            "/api/v1/products",
            json={"name": name, "category_id": str(category.id), "vendor_sku": "SHARED-1"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    assert db_session.query(Product).filter_by(vendor_sku="SHARED-1").count() == 2
