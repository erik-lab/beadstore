import datetime
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
