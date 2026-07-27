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
