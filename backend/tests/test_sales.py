import datetime


def _create_product(client, auth_headers, name="Test bead"):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    return client.post(
        "/api/v1/products", json={"name": name, "category_id": category["id"]}, headers=auth_headers
    ).json()


def _add_inventory(client, auth_headers, product_id, quantity, received_date="2026-01-01"):
    return client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product_id,
            "quantity": quantity,
            "unit_type": "strand",
            "received_date": received_date,
        },
        headers=auth_headers,
    ).json()


def test_create_sale_decrements_inventory(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 10)

    resp = client.post(
        "/api/v1/sales",
        json={"lines": [{"product_id": product["id"], "quantity": 3, "unit_price": 5.5}]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    sale = resp.json()
    assert sale["status"] == "recorded"
    assert len(sale["lines"]) == 1
    assert sale["lines"][0]["quantity"] == 3

    units = client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()
    assert units[0]["quantity"] == 7


def test_create_sale_consumes_fifo_across_multiple_units(client, auth_headers):
    product = _create_product(client, auth_headers)
    oldest = _add_inventory(client, auth_headers, product["id"], 5, received_date="2026-01-01")
    newest = _add_inventory(client, auth_headers, product["id"], 5, received_date="2026-02-01")

    resp = client.post(
        "/api/v1/sales",
        json={"lines": [{"product_id": product["id"], "quantity": 8}]},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    units = {u["id"]: u for u in client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()}
    # oldest unit fully consumed (5), newest unit partially consumed (3 of 5 taken, 2 left)
    assert units[oldest["id"]]["quantity"] == 0
    assert units[oldest["id"]]["status"] == "depleted"
    assert units[newest["id"]]["quantity"] == 2
    assert units[newest["id"]]["status"] == "available"


def test_create_sale_rejects_insufficient_stock(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 2)

    resp = client.post(
        "/api/v1/sales",
        json={"lines": [{"product_id": product["id"], "quantity": 5}]},
        headers=auth_headers,
    )
    assert resp.status_code == 409

    # nothing should have been decremented by the rejected sale
    units = client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()
    assert units[0]["quantity"] == 2


def test_create_sale_aggregates_demand_across_lines_for_same_product(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 5)

    # two lines each individually <= 5, but together they exceed on-hand stock
    resp = client.post(
        "/api/v1/sales",
        json={
            "lines": [
                {"product_id": product["id"], "quantity": 3},
                {"product_id": product["id"], "quantity": 4},
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 409

    units = client.get(f"/api/v1/products/{product['id']}/inventory-units", headers=auth_headers).json()
    assert units[0]["quantity"] == 5


def test_create_sale_requires_at_least_one_line(client, auth_headers):
    resp = client.post("/api/v1/sales", json={"lines": []}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_sale_rejects_unknown_product(client, auth_headers):
    resp = client.post(
        "/api/v1/sales",
        json={"lines": [{"product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_list_and_get_sale(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 10)
    created = client.post(
        "/api/v1/sales",
        json={"channel": "etsy", "external_order_id": "ETSY-123", "lines": [{"product_id": product["id"], "quantity": 1}]},
        headers=auth_headers,
    ).json()

    resp = client.get("/api/v1/sales", headers=auth_headers)
    assert any(s["id"] == created["id"] for s in resp.json())

    resp = client.get(f"/api/v1/sales/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["external_order_id"] == "ETSY-123"
    assert resp.json()["lines"][0]["product_name"] == "Test bead"


def test_sales_require_staff_auth(client):
    resp = client.get("/api/v1/sales")
    assert resp.status_code == 401
