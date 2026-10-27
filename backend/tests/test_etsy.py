import datetime
import uuid
from urllib.parse import urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app as fastapi_app
from app.services import etsy_service

settings = get_settings()


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "etsy_client_id", "test-keystring")
    monkeypatch.setattr(settings, "etsy_client_secret", "test-secret")
    monkeypatch.setattr(settings, "etsy_webhook_signing_secret", "test-webhook-secret")
    # All three bases point at the simulator, which mirrors real Etsy's
    # relative paths under one origin. Against real Etsy these differ
    # (www.etsy.com / api.etsy.com / openapi.etsy.com).
    monkeypatch.setattr(settings, "etsy_api_base_url", "http://simulator/etsy-simulator")
    monkeypatch.setattr(settings, "etsy_token_base_url", "http://simulator/etsy-simulator")
    monkeypatch.setattr(settings, "etsy_authorize_base_url", "http://simulator/etsy-simulator")

    # Route etsy_service's httpx calls through the in-process app (real
    # network sockets aren't available/needed here) rather than to the live
    # internet — see conftest.py for why the simulator router is mounted on
    # this same `app` object for the whole test session. TestClient (not a
    # raw httpx.Client+ASGITransport) specifically because it bridges the
    # ASGI app's async handlers into the sync calls etsy_service.py makes
    # (matching gmail_service.py/outlook_service.py's style) — ASGITransport
    # alone only supports httpx.AsyncClient.
    test_transport_client = TestClient(fastapi_app, base_url="http://simulator")
    monkeypatch.setattr(etsy_service.httpx, "get", test_transport_client.get)
    monkeypatch.setattr(etsy_service.httpx, "post", test_transport_client.post)
    monkeypatch.setattr(etsy_service.httpx, "put", test_transport_client.put)
    # delete and patch are needed too, for listing-image removal and the
    # state change that activates a listing.
    monkeypatch.setattr(etsy_service.httpx, "delete", test_transport_client.delete)
    monkeypatch.setattr(etsy_service.httpx, "patch", test_transport_client.patch)

    from app.etsy_simulator.state import store

    store.reset()
    yield
    test_transport_client.close()


def _create_product(client, auth_headers, name="Test bead"):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    return client.post(
        "/api/v1/products", json={"name": name, "category_id": category["id"]}, headers=auth_headers
    ).json()


def _create_listing(client, auth_headers, product_id, price=9.99):
    return client.post(
        "/api/v1/catalog-listings",
        json={"product_id": product_id, "title": "Etsy Test Listing", "status": "published", "price": price},
        headers=auth_headers,
    ).json()


def _connect_shop(client, auth_headers):
    """Drives the full browser-navigation OAuth dance through our own
    endpoints and the simulator, exactly as a real connect would (minus an
    actual browser): GET /etsy/connect -> follow the authorize redirect ->
    GET /etsy/callback.
    """
    connect = client.get("/api/v1/etsy/connect", headers=auth_headers)
    assert connect.status_code == 200
    authorize_url = connect.json()["url"]
    parsed = urlparse(authorize_url)

    redirect = client.get(f"{parsed.path}?{parsed.query}", follow_redirects=False)
    assert redirect.status_code == 307
    callback_url = urlparse(redirect.headers["location"])
    assert callback_url.path == "/api/v1/etsy/callback"

    callback = client.get(f"{callback_url.path}?{callback_url.query}")
    assert callback.status_code == 200
    return callback


def test_connect_requires_staff_auth(client):
    resp = client.get("/api/v1/etsy/connect")
    assert resp.status_code == 401


def test_production_urls_are_built_against_the_real_etsy_hosts(monkeypatch):
    """Pins what the simulator can't check.

    Every path is appended to a base that holds an origin only, and all three
    bases are the same host in local dev — so pointing a base at
    ".../v3" would silently produce /v3/v3/... and only fail against live
    Etsy. These are the hosts and paths Etsy's auth guide documents.
    """
    monkeypatch.setattr(settings, "etsy_authorize_base_url", "https://www.etsy.com")
    monkeypatch.setattr(settings, "etsy_token_base_url", "https://api.etsy.com")
    monkeypatch.setattr(settings, "etsy_api_base_url", "https://openapi.etsy.com")

    authorize_url = etsy_service.build_authorize_url("https://app.example/cb", "state", "challenge")
    assert authorize_url.startswith("https://www.etsy.com/oauth/connect?")

    assert (
        f"{settings.etsy_token_base_url}{etsy_service.TOKEN_PATH}"
        == "https://api.etsy.com/v3/public/oauth/token"
    )

    # No doubled /v3 on the API paths.
    for base, path in (
        (settings.etsy_api_base_url, "/v3/application/shops/123"),
        (settings.etsy_api_base_url, "/v3/application/users/7/shops"),
    ):
        url = f"{base}{path}"
        assert url.startswith("https://openapi.etsy.com/v3/application/")
        assert "/v3/v3/" not in url


def test_default_base_urls_hold_origins_only():
    """A default with a version path on it is the bug this guards against."""
    defaults = Settings()
    for base in (
        defaults.etsy_authorize_base_url,
        defaults.etsy_token_base_url,
        defaults.etsy_api_base_url,
    ):
        assert not base.rstrip("/").endswith("/v3"), f"{base} should be an origin, not a versioned path"


def test_full_oauth_flow_creates_account(client, auth_headers):
    _connect_shop(client, auth_headers)

    resp = client.get("/api/v1/etsy/accounts", headers=auth_headers)
    assert resp.status_code == 200
    accounts = resp.json()
    assert len(accounts) == 1
    assert accounts[0]["status"] == "active"
    assert accounts[0]["shop_name"] == "Patti's Test Shop"


def test_push_listing_requires_connected_shop(client, auth_headers):
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])

    resp = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push",
        json={"taxonomy_id": 1, "shipping_profile_id": 1, "return_policy_id": 1, "who_made": "i_did", "when_made": "made_to_order"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_push_listing_requires_etsy_fields(client, auth_headers):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])

    resp = client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "taxonomy_id" in resp.json()["detail"]


def test_push_listing_creates_draft_then_updates_on_second_push(client, auth_headers):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])

    payload = {
        "taxonomy_id": 100,
        "shipping_profile_id": 200,
        "return_policy_id": 300,
        "who_made": "i_did",
        "when_made": "made_to_order",
    }
    first = client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json=payload, headers=auth_headers)
    assert first.status_code == 200
    body = first.json()
    assert body["sync_status"] == "synced"
    assert body["etsy_listing_id"] is not None
    first_etsy_id = body["etsy_listing_id"]

    second = client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json={}, headers=auth_headers)
    assert second.status_code == 200
    assert second.json()["etsy_listing_id"] == first_etsy_id
    assert second.json()["sync_status"] == "synced"


def test_pull_receipts_creates_sale_and_decrements_inventory(client, auth_headers):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    client.post(
        "/api/v1/inventory-units",
        json={"product_id": product["id"], "quantity": 10, "unit_type": "strand", "received_date": str(datetime.date.today())},
        headers=auth_headers,
    )
    listing = _create_listing(client, auth_headers, product["id"], price=12.5)
    push = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push",
        json={"taxonomy_id": 1, "shipping_profile_id": 1, "return_policy_id": 1, "who_made": "i_did", "when_made": "made_to_order"},
        headers=auth_headers,
    ).json()

    accounts = client.get("/api/v1/etsy/accounts", headers=auth_headers).json()
    shop_id = accounts[0]["shop_id"]
    seed = client.post(
        "http://simulator/etsy-simulator/_simulator/seed-receipt",
        json={"shop_id": shop_id, "listing_id": push["etsy_listing_id"], "quantity": 3, "price": 12.5},
    )
    assert seed.status_code == 200

    resp = client.post("/api/v1/etsy/pull", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "skipped_unmapped": 0, "skipped_duplicate": 0}

    units = client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()
    assert units[0]["quantity"] == 7

    sales = client.get("/api/v1/sales?limit=50", headers=auth_headers).json()
    etsy_sales = [s for s in sales if s["channel"] == "etsy"]
    assert len(etsy_sales) == 1

    # pulling again must not double-count the same receipt
    resp = client.post("/api/v1/etsy/pull", headers=auth_headers)
    assert resp.json()["skipped_duplicate"] == 1
    units = client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()
    assert units[0]["quantity"] == 7


def test_simulate_sale_lets_pull_find_a_real_order(client, auth_headers):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    client.post(
        "/api/v1/inventory-units",
        json={"product_id": product["id"], "quantity": 10, "unit_type": "strand", "received_date": str(datetime.date.today())},
        headers=auth_headers,
    )
    listing = _create_listing(client, auth_headers, product["id"], price=12.5)
    push = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push",
        json={"taxonomy_id": 1, "shipping_profile_id": 1, "return_policy_id": 1, "who_made": "i_did", "when_made": "made_to_order"},
        headers=auth_headers,
    ).json()

    resp = client.post(
        "/api/v1/etsy/simulate-sale",
        json={"catalog_listing_id": listing["id"], "quantity": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    pull = client.post("/api/v1/etsy/pull", headers=auth_headers)
    assert pull.json() == {"created": 1, "skipped_unmapped": 0, "skipped_duplicate": 0}

    units = client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()
    assert units[0]["quantity"] == 8


def test_simulate_sale_requires_listing_to_be_pushed_first(client, auth_headers):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])

    resp = client.post(
        "/api/v1/etsy/simulate-sale",
        json={"catalog_listing_id": listing["id"], "quantity": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_simulate_sale_requires_staff_auth(client):
    resp = client.post("/api/v1/etsy/simulate-sale", json={"catalog_listing_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 401


def test_webhook_rejects_bad_signature(client):
    resp = client.post(
        "/api/v1/etsy/webhook",
        content=b'{"event_type": "order.paid", "receipt_id": "123"}',
        headers={"X-Etsy-Signature": "not-the-real-signature", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_webhook_triggers_pull_with_valid_signature(client, auth_headers):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    client.post(
        "/api/v1/inventory-units",
        json={"product_id": product["id"], "quantity": 5, "unit_type": "strand", "received_date": str(datetime.date.today())},
        headers=auth_headers,
    )
    listing = _create_listing(client, auth_headers, product["id"])
    push = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push",
        json={"taxonomy_id": 1, "shipping_profile_id": 1, "return_policy_id": 1, "who_made": "i_did", "when_made": "made_to_order"},
        headers=auth_headers,
    ).json()
    accounts = client.get("/api/v1/etsy/accounts", headers=auth_headers).json()
    client.post(
        "http://simulator/etsy-simulator/_simulator/seed-receipt",
        json={"shop_id": accounts[0]["shop_id"], "listing_id": push["etsy_listing_id"], "quantity": 1, "price": 9.99},
    )

    import hashlib
    import hmac

    body = b'{"event_type": "order.paid"}'
    signature = hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    resp = client.post(
        "/api/v1/etsy/webhook",
        content=body,
        headers={"X-Etsy-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1


def test_shipping_profile_and_return_policy_dropdowns(client, auth_headers):
    """The Etsy-only required IDs have to be pickable, not typed from memory."""
    _connect_shop(client, auth_headers)

    profiles = client.get("/api/v1/etsy/shipping-profiles", headers=auth_headers)
    assert profiles.status_code == 200
    assert profiles.json() == [
        {"id": "901", "label": "Standard US"},
        {"id": "902", "label": "US + International"},
    ]

    policies = client.get("/api/v1/etsy/return-policies", headers=auth_headers)
    assert policies.status_code == 200
    # Etsy gives return policies no title, so the label is built from terms.
    assert policies.json() == [
        {"id": "701", "label": "Accepts returns within 30 days, exchanges allowed"},
        {"id": "702", "label": "No returns or exchanges"},
    ]


def test_taxonomy_search_returns_full_category_paths(client, auth_headers):
    _connect_shop(client, auth_headers)

    resp = client.get("/api/v1/etsy/taxonomy?search=beads", headers=auth_headers)
    assert resp.status_code == 200
    options = resp.json()

    labels = [option["label"] for option in options]
    # The path is the point: "Beads" alone appears in more than one branch.
    assert "Craft Supplies & Tools > Beads, Gems & Cabochons > Beads" in labels
    # "beads" has to reach "Beaded Necklaces" too — Etsy's category names are
    # inconsistent about plurals and word forms, and the reviewer types the
    # word they'd use, not Etsy's.
    assert "Jewelry > Necklaces > Beaded Necklaces" in labels
    # A match on the node's own name outranks one buried in an ancestor path,
    # and the tightest of those comes first.
    assert labels[0] == "Craft Supplies & Tools > Beads, Gems & Cabochons > Beads"

    by_label = {option["label"]: option["id"] for option in options}
    assert by_label["Craft Supplies & Tools > Beads, Gems & Cabochons > Beads"] == "111"


def test_taxonomy_search_narrows_and_limit_applies(client, auth_headers):
    _connect_shop(client, auth_headers)

    unfiltered = client.get("/api/v1/etsy/taxonomy", headers=auth_headers).json()
    assert len(unfiltered) > 5

    # Matching the whole path means a search for "cabochons" also catches
    # everything filed under "Beads, Gems & Cabochons" — so what matters is
    # that the node actually named Cabochons ranks first.
    narrowed = client.get("/api/v1/etsy/taxonomy?search=cabochons", headers=auth_headers).json()
    assert narrowed[0]["label"] == "Craft Supplies & Tools > Beads, Gems & Cabochons > Cabochons"
    assert all("cabochon" in o["label"].lower() for o in narrowed)

    capped = client.get("/api/v1/etsy/taxonomy?limit=2", headers=auth_headers).json()
    assert len(capped) == 2


def test_option_lookups_need_a_connected_shop(client, auth_headers):
    for path in ("/api/v1/etsy/shipping-profiles", "/api/v1/etsy/return-policies"):
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code == 409
        assert "No active Etsy shop" in resp.json()["detail"]


def test_option_lookups_require_staff_auth(client):
    for path in ("/api/v1/etsy/shipping-profiles", "/api/v1/etsy/return-policies", "/api/v1/etsy/taxonomy"):
        assert client.get(path).status_code == 401


def test_push_sends_the_shop_sku_to_etsy_on_the_first_push(client, auth_headers):
    """Etsy keeps the SKU on a listing's inventory, not on the listing.

    So inventory is updated straight after a create — otherwise the listing
    would sit there without a SKU until some later push happened along, and
    an incoming order couldn't be tied back to the product by code.
    """
    from app.etsy_simulator.state import store
    from app.services import sku_service

    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])

    resp = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push",
        json={
            "taxonomy_id": 100,
            "shipping_profile_id": 200,
            "return_policy_id": 300,
            "who_made": "i_did",
            "when_made": "made_to_order",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    etsy_listing_id = resp.json()["etsy_listing_id"]

    stored = store.listings[etsy_listing_id]
    assert stored["products"], "inventory should have been set on the first push"
    assert stored["products"][0]["sku"] == product["sku"]
    assert sku_service.is_valid_sku(stored["products"][0]["sku"])


# --------------------------------------------------------------------------
# Listing images and activation
# --------------------------------------------------------------------------

PUSH_FIELDS = {
    "taxonomy_id": 100,
    "shipping_profile_id": 200,
    "return_policy_id": 300,
    "who_made": "i_did",
    "when_made": "made_to_order",
}


@pytest.fixture()
def product_photos(tmp_path, monkeypatch):
    """Point photo storage at a temp directory for these tests."""
    from app.core import storage

    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "storage_local_root", str(tmp_path / "uploads"))
    storage.get_object_store.cache_clear()
    yield
    storage.get_object_store.cache_clear()


def _add_photo(client, auth_headers, product_id, colour=(120, 40, 90)):
    import base64
    import io

    from PIL import Image

    image = Image.new("RGB", (600, 400), (200, 200, 200))
    image.paste(Image.new("RGB", (300, 200), colour), (0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")

    resp = client.post(
        f"/api/v1/products/{product_id}/images",
        json={"filename": "bead.jpg", "data_base64": base64.b64encode(buffer.getvalue()).decode()},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


def _etsy_images(etsy_listing_id):
    from app.etsy_simulator.state import store

    return store.listings[etsy_listing_id].get("images", [])


def test_push_uploads_photos_to_etsy_in_order(client, auth_headers, product_photos):
    """The multipart upload path, driven against the simulator for real."""
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    first = _add_photo(client, auth_headers, product["id"], colour=(10, 20, 200))
    second = _add_photo(client, auth_headers, product["id"], colour=(200, 20, 10))
    listing = _create_listing(client, auth_headers, product["id"])

    resp = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers
    )
    assert resp.status_code == 200, resp.json()
    etsy_listing_id = resp.json()["etsy_listing_id"]
    assert resp.json()["etsy_state"] == "draft"

    images = _etsy_images(etsy_listing_id)
    assert [image["rank"] for image in images] == [1, 2]
    assert all(image["byte_size"] > 0 for image in images), "the file itself should have arrived"
    assert images[0]["filename"] == "bead.jpg"
    # Local order is Etsy's order; rank 1 is what Etsy shows in search.
    assert len(images) == 2
    assert first["id"] != second["id"]


def test_alt_text_is_sent_with_the_image(client, auth_headers, product_photos):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    image = _add_photo(client, auth_headers, product["id"])
    client.patch(
        f"/api/v1/products/images/{image['id']}",
        json={"alt_text": "Matte black rounds"},
        headers=auth_headers,
    )
    listing = _create_listing(client, auth_headers, product["id"])

    resp = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers
    )
    assert _etsy_images(resp.json()["etsy_listing_id"])[0]["alt_text"] == "Matte black rounds"


def test_pushing_again_without_photo_changes_does_not_re_upload(
    client, auth_headers, product_photos
):
    """A price-only sync must not churn the images."""
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    _add_photo(client, auth_headers, product["id"])
    listing = _create_listing(client, auth_headers, product["id"])

    first = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers
    ).json()
    etsy_listing_id = first["etsy_listing_id"]
    original_ids = [image["listing_image_id"] for image in _etsy_images(etsy_listing_id)]

    client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json={}, headers=auth_headers)
    assert [image["listing_image_id"] for image in _etsy_images(etsy_listing_id)] == original_ids


def test_reordering_photos_locally_reorders_them_on_etsy(client, auth_headers, product_photos):
    """Etsy fixes rank at upload with no reorder call, so a changed order has
    to be re-sent — otherwise the wrong photo stays primary."""
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    first = _add_photo(client, auth_headers, product["id"], colour=(10, 20, 200))
    second = _add_photo(client, auth_headers, product["id"], colour=(200, 20, 10))
    listing = _create_listing(client, auth_headers, product["id"])

    push = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers
    ).json()
    etsy_listing_id = push["etsy_listing_id"]
    before = _etsy_images(etsy_listing_id)
    primary_size_before = before[0]["byte_size"]

    client.patch(
        f"/api/v1/products/{product['id']}/images/reorder",
        json={"image_ids": [second["id"], first["id"]]},
        headers=auth_headers,
    )
    client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json={}, headers=auth_headers)

    after = _etsy_images(etsy_listing_id)
    assert [image["rank"] for image in after] == [1, 2]
    assert len(after) == 2, "re-sending must not leave the old copies behind"
    # The photo at rank 1 is now the other one.
    assert after[0]["byte_size"] != primary_size_before


def test_deleting_a_photo_removes_it_from_etsy(client, auth_headers, product_photos):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    keep = _add_photo(client, auth_headers, product["id"], colour=(10, 20, 200))
    remove = _add_photo(client, auth_headers, product["id"], colour=(200, 20, 10))
    listing = _create_listing(client, auth_headers, product["id"])

    push = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers
    ).json()
    etsy_listing_id = push["etsy_listing_id"]
    assert len(_etsy_images(etsy_listing_id)) == 2

    client.delete(f"/api/v1/products/images/{remove['id']}", headers=auth_headers)
    client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json={}, headers=auth_headers)

    assert len(_etsy_images(etsy_listing_id)) == 1
    assert keep["id"] is not None


def test_activating_makes_the_listing_live(client, auth_headers, product_photos):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    _add_photo(client, auth_headers, product["id"])
    listing = _create_listing(client, auth_headers, product["id"])
    push = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers
    ).json()

    resp = client.post(f"/api/v1/etsy/listings/{listing['id']}/activate", headers=auth_headers)
    assert resp.status_code == 200, resp.json()
    assert resp.json()["etsy_state"] == "active"

    from app.etsy_simulator.state import store

    assert store.listings[push["etsy_listing_id"]]["state"] == "active"


def test_pushing_never_activates_by_itself(client, auth_headers, product_photos):
    """Going live is what Etsy's per-listing fee pays for — a stock sync
    must not be able to trigger it as a side effect."""
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    _add_photo(client, auth_headers, product["id"])
    listing = _create_listing(client, auth_headers, product["id"])

    push = client.post(
        f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers
    ).json()
    assert push["etsy_state"] == "draft"

    from app.etsy_simulator.state import store

    assert store.listings[push["etsy_listing_id"]]["state"] == "draft"


def test_activating_without_a_photo_is_refused_before_calling_etsy(client, auth_headers, product_photos):
    """Etsy refuses this too; saying so here explains what to do about it."""
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])
    client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers)

    resp = client.post(f"/api/v1/etsy/listings/{listing['id']}/activate", headers=auth_headers)
    assert resp.status_code == 409
    assert "no photos" in resp.json()["detail"]


def test_the_simulator_refuses_to_activate_without_images(client, auth_headers, product_photos):
    """The Etsy-side constraint, not just our own pre-check.

    Our pre-check is bypassed by recording a sham image row, so the request
    actually reaches the simulator and is refused there — proving the
    prerequisite is modelled on the Etsy side too.
    """
    from app.models.etsy_listing_image import EtsyListingImage
    from app.models.etsy_listing_sync import EtsyListingSync

    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])
    client.post(f"/api/v1/etsy/listings/{listing['id']}/push", json=PUSH_FIELDS, headers=auth_headers)

    from app.core.db import get_db

    db = next(fastapi_app.dependency_overrides[get_db]())
    sync_row = db.query(EtsyListingSync).one()
    db.add(
        EtsyListingImage(
            etsy_listing_sync_id=sync_row.id,
            product_image_id=None,
            etsy_image_id="not-really-there",
            rank=1,
        )
    )
    db.commit()

    resp = client.post(f"/api/v1/etsy/listings/{listing['id']}/activate", headers=auth_headers)
    assert resp.status_code == 502
    assert "at least one image" in str(resp.json()["detail"])


def test_activating_an_unpushed_listing_is_refused(client, auth_headers, product_photos):
    _connect_shop(client, auth_headers)
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"])

    resp = client.post(f"/api/v1/etsy/listings/{listing['id']}/activate", headers=auth_headers)
    assert resp.status_code == 409
    assert "hasn't been pushed" in resp.json()["detail"]


def test_activate_requires_staff_auth(client):
    assert client.post(f"/api/v1/etsy/listings/{uuid.uuid4()}/activate").status_code == 401
