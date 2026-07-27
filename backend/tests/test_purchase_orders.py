def _create_vendor(client, auth_headers, name="Sunrise Bead Supply"):
    return client.post("/api/v1/vendors", json={"name": name}, headers=auth_headers).json()


def test_create_purchase_order_with_lines(client, auth_headers):
    vendor = _create_vendor(client, auth_headers)
    resp = client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": vendor["id"],
            "lines": [
                {"expected_item_description": "10 strands 6mm amethyst", "expected_quantity": 10, "expected_unit_type": "strand"},
                {"expected_item_description": "unknown findings assortment"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    po = resp.json()
    assert po["status"] == "draft"
    assert len(po["lines"]) == 2


def test_purchase_order_line_requires_product_or_description(client, auth_headers):
    vendor = _create_vendor(client, auth_headers)
    resp = client.post(
        "/api/v1/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"expected_quantity": 5}]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_mark_purchase_order_ordered(client, auth_headers):
    vendor = _create_vendor(client, auth_headers)
    po = client.post("/api/v1/purchase-orders", json={"vendor_id": vendor["id"]}, headers=auth_headers).json()
    resp = client.post(f"/api/v1/purchase-orders/{po['id']}/mark-ordered", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


def test_add_line_to_existing_order(client, auth_headers):
    vendor = _create_vendor(client, auth_headers)
    po = client.post("/api/v1/purchase-orders", json={"vendor_id": vendor["id"]}, headers=auth_headers).json()
    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/lines",
        json={"expected_item_description": "New line", "expected_quantity": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "expected"
