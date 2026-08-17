import datetime


def _create_product(client, auth_headers, name="Test bead"):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    return client.post(
        "/api/v1/products", json={"name": name, "category_id": category["id"]}, headers=auth_headers
    ).json()


def _add_inventory(client, auth_headers, product_id, quantity):
    client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product_id,
            "quantity": quantity,
            "unit_type": "strand",
            "received_date": str(datetime.date.today()),
        },
        headers=auth_headers,
    )


def _create_listing(client, auth_headers, product_id, status="published", price=9.99, **extra):
    payload = {"product_id": product_id, "title": "Storefront Listing", "status": status, "price": price, **extra}
    return client.post("/api/v1/catalog-listings", json=payload, headers=auth_headers).json()


def _storefront_key(client, auth_headers, kind="storefront"):
    created = client.post("/api/v1/api-clients", json={"name": "Test", "kind": kind}, headers=auth_headers).json()
    return created["api_key"]


def test_storefront_requires_api_key(client):
    resp = client.get("/api/v1/storefront/listings")
    assert resp.status_code == 401


def test_storefront_rejects_non_storefront_key(client, auth_headers):
    etsy_key = _storefront_key(client, auth_headers, kind="etsy")
    resp = client.get("/api/v1/storefront/listings", headers={"X-API-Key": etsy_key})
    assert resp.status_code == 403


def test_storefront_lists_only_published_listings(client, auth_headers):
    product = _create_product(client, auth_headers)
    _create_listing(client, auth_headers, product["id"], status="published")
    _create_listing(client, auth_headers, product["id"], status="draft")
    key = _storefront_key(client, auth_headers)

    resp = client.get("/api/v1/storefront/listings", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Storefront Listing"


def test_storefront_listing_excludes_internal_fields(client, auth_headers):
    product = _create_product(client, auth_headers)
    listing = _create_listing(
        client, auth_headers, product["id"], listing_notes="internal reorder note", publish_readiness="ready"
    )
    key = _storefront_key(client, auth_headers)

    resp = client.get(f"/api/v1/storefront/listings/{listing['id']}", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert "listing_notes" not in body
    assert "publish_readiness" not in body
    assert "status" not in body
    assert "product_id" not in body


def test_storefront_get_unpublished_listing_404(client, auth_headers):
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"], status="draft")
    key = _storefront_key(client, auth_headers)

    resp = client.get(f"/api/v1/storefront/listings/{listing['id']}", headers={"X-API-Key": key})
    assert resp.status_code == 404


def test_storefront_available_quantity_reflects_derived_mode(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 6)
    listing = _create_listing(
        client, auth_headers, product["id"], available_quantity_mode="derived_from_inventory"
    )
    key = _storefront_key(client, auth_headers)

    resp = client.get(f"/api/v1/storefront/listings/{listing['id']}", headers={"X-API-Key": key})
    assert resp.json()["available_quantity"] == 6


def test_storefront_create_order_ignores_client_supplied_price(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 10)
    listing = _create_listing(client, auth_headers, product["id"], price=42.00)
    key = _storefront_key(client, auth_headers)

    resp = client.post(
        "/api/v1/storefront/orders",
        json={"lines": [{"catalog_listing_id": listing["id"], "quantity": 2}]},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 201
    sale = resp.json()
    assert sale["lines"][0]["unit_price"] == 42.00
    assert sale["lines"][0]["quantity"] == 2

    units = client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()
    assert units[0]["quantity"] == 8


def test_storefront_create_order_rejects_unpublished_listing(client, auth_headers):
    product = _create_product(client, auth_headers)
    listing = _create_listing(client, auth_headers, product["id"], status="draft")
    key = _storefront_key(client, auth_headers)

    resp = client.post(
        "/api/v1/storefront/orders",
        json={"lines": [{"catalog_listing_id": listing["id"], "quantity": 1}]},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 404


def test_storefront_created_sale_is_visible_in_staff_sales_list(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 5)
    listing = _create_listing(client, auth_headers, product["id"])
    key = _storefront_key(client, auth_headers)

    created = client.post(
        "/api/v1/storefront/orders",
        json={"lines": [{"catalog_listing_id": listing["id"], "quantity": 1}]},
        headers={"X-API-Key": key},
    ).json()

    resp = client.get(f"/api/v1/sales/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["channel"] == "storefront"
