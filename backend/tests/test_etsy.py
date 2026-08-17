import datetime
from urllib.parse import urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app as fastapi_app
from app.services import etsy_service

settings = get_settings()


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "etsy_client_id", "test-keystring")
    monkeypatch.setattr(settings, "etsy_client_secret", "test-secret")
    monkeypatch.setattr(settings, "etsy_webhook_signing_secret", "test-webhook-secret")
    monkeypatch.setattr(settings, "etsy_api_base_url", "http://simulator/etsy-simulator")

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
