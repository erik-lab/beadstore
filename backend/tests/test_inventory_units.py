import datetime


def _create_product(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Test bead", "category_id": category["id"]}, headers=auth_headers
    ).json()
    return product


def test_create_inventory_unit_requires_product_or_description(client, auth_headers):
    resp = client.post(
        "/api/v1/inventory-units",
        json={
            "quantity": 3,
            "unit_type": "strand",
            "received_date": str(datetime.date.today()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_inventory_unit_with_product(client, auth_headers):
    product = _create_product(client, auth_headers)
    resp = client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product["id"],
            "quantity": 4,
            "unit_type": "strand",
            "received_date": str(datetime.date.today()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    unit = resp.json()
    assert unit["quantity"] == 4
    assert unit["status"] == "available"


def test_inventory_unit_supports_unresolved_description(client, auth_headers):
    resp = client.post(
        "/api/v1/inventory-units",
        json={
            "unresolved_description": "Mystery bag of beads",
            "quantity": 1,
            "unit_type": "bag",
            "status": "unresolved",
            "received_date": str(datetime.date.today()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["unresolved_description"] == "Mystery bag of beads"


def test_inventory_adjustment_changes_quantity(client, auth_headers):
    product = _create_product(client, auth_headers)
    unit = client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product["id"],
            "quantity": 10,
            "unit_type": "count",
            "received_date": str(datetime.date.today()),
        },
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/v1/inventory-units/{unit['id']}/adjustments",
        json={"adjustment_type": "count_correction", "quantity_delta": -2, "reason": "recount"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 8
