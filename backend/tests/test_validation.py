def test_vendor_requires_name(client, auth_headers):
    resp = client.post("/api/v1/vendors", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_location_requires_name(client, auth_headers):
    resp = client.post("/api/v1/locations", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_purchase_order_requires_vendor(client, auth_headers):
    resp = client.post("/api/v1/purchase-orders", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_receipt_line_requires_quantity_and_unit_type(client, auth_headers):
    vendor = client.post("/api/v1/vendors", json={"name": "Vendor"}, headers=auth_headers).json()
    po = client.post("/api/v1/purchase-orders", json={"vendor_id": vendor["id"]}, headers=auth_headers).json()

    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"unresolved_item_description": "Something"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_get_missing_product_returns_404(client, auth_headers):
    resp = client.get("/api/v1/products/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


def test_vendor_name_rejects_blank_and_whitespace(client, auth_headers):
    assert client.post("/api/v1/vendors", json={"name": ""}, headers=auth_headers).status_code == 422
    assert client.post("/api/v1/vendors", json={"name": "   "}, headers=auth_headers).status_code == 422


def test_vendor_name_is_trimmed(client, auth_headers):
    resp = client.post("/api/v1/vendors", json={"name": "  Sunrise Bead Supply  "}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Sunrise Bead Supply"


def test_vendor_rejects_malformed_email(client, auth_headers):
    resp = client.post("/api/v1/vendors", json={"name": "Vendor", "email": "not-an-email"}, headers=auth_headers)
    assert resp.status_code == 422


def test_vendor_accepts_valid_email(client, auth_headers):
    resp = client.post(
        "/api/v1/vendors", json={"name": "Vendor", "email": "orders@example.com"}, headers=auth_headers
    )
    assert resp.status_code == 201


def test_product_name_rejects_blank(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    resp = client.post(
        "/api/v1/products", json={"name": "   ", "category_id": category["id"]}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_inventory_unit_rejects_zero_and_negative_quantity(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Bead", "category_id": category["id"]}, headers=auth_headers
    ).json()
    for bad_quantity in (0, -5):
        resp = client.post(
            "/api/v1/inventory-units",
            json={
                "product_id": product["id"],
                "quantity": bad_quantity,
                "unit_type": "strand",
                "received_date": "2026-01-01",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422


def test_inventory_unit_rejects_negative_cost(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Bead", "category_id": category["id"]}, headers=auth_headers
    ).json()
    resp = client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product["id"],
            "quantity": 5,
            "unit_type": "strand",
            "received_date": "2026-01-01",
            "cost_amount": -1,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_inventory_adjustment_rejects_zero_delta(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Bead", "category_id": category["id"]}, headers=auth_headers
    ).json()
    unit = client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product["id"],
            "quantity": 5,
            "unit_type": "strand",
            "received_date": "2026-01-01",
        },
        headers=auth_headers,
    ).json()
    resp = client.post(
        f"/api/v1/inventory-units/{unit['id']}/adjustments",
        json={"adjustment_type": "manual_correction", "quantity_delta": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_inventory_adjustment_rejects_going_below_zero(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Bead", "category_id": category["id"]}, headers=auth_headers
    ).json()
    unit = client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product["id"],
            "quantity": 5,
            "unit_type": "strand",
            "received_date": "2026-01-01",
        },
        headers=auth_headers,
    ).json()
    resp = client.post(
        f"/api/v1/inventory-units/{unit['id']}/adjustments",
        json={"adjustment_type": "damaged", "quantity_delta": -10},
        headers=auth_headers,
    )
    assert resp.status_code == 400

    # the unit's quantity must be unchanged after the rejected adjustment
    refreshed = client.get(f"/api/v1/inventory-units/{unit['id']}", headers=auth_headers).json()
    assert refreshed["quantity"] == 5


def test_receive_line_rejects_zero_quantity(client, auth_headers):
    vendor = client.post("/api/v1/vendors", json={"name": "Vendor"}, headers=auth_headers).json()
    po = client.post("/api/v1/purchase-orders", json={"vendor_id": vendor["id"]}, headers=auth_headers).json()
    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"unresolved_item_description": "Something", "received_quantity": 0, "received_unit_type": "strand"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 422
