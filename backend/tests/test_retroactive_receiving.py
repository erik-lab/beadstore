def test_quick_receive_creates_retroactive_order(client, auth_headers):
    vendor = client.post("/api/v1/vendors", json={"name": "Walk-in Supplier"}, headers=auth_headers).json()

    resp = client.post(
        "/api/v1/receiving/quick-receive",
        json={
            "vendor_id": vendor["id"],
            "lines": [
                {"unresolved_item_description": "Bag of assorted clasps", "received_quantity": 1, "received_unit_type": "bag"}
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["purchase_order_status"] == "received"

    po = client.get(f"/api/v1/purchase-orders/{result['purchase_order_id']}", headers=auth_headers).json()
    assert po["is_retroactive"] is True
    assert "receiving" in po["notes"].lower()
    assert len(po["lines"]) == 1

    receipts = client.get(f"/api/v1/purchase-orders/{po['id']}/receipts", headers=auth_headers).json()
    assert len(receipts) == 1
    assert len(receipts[0]["lines"]) == 1


def test_quick_receive_with_known_product(client, auth_headers):
    vendor = client.post("/api/v1/vendors", json={"name": "Walk-in Supplier"}, headers=auth_headers).json()
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Known bead", "category_id": category["id"]}, headers=auth_headers
    ).json()

    resp = client.post(
        "/api/v1/receiving/quick-receive",
        json={
            "vendor_id": vendor["id"],
            "lines": [{"product_id": product["id"], "received_quantity": 3, "received_unit_type": "strand"}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["summary"]["matched"] == 1

    inv = client.get(f"/api/v1/inventory-units?product_id={product['id']}", headers=auth_headers).json()
    assert len(inv) == 1
    assert inv[0]["quantity"] == 3


def test_resolve_unresolved_receipt_line(client, auth_headers):
    vendor = client.post("/api/v1/vendors", json={"name": "Walk-in Supplier"}, headers=auth_headers).json()
    category = client.post("/api/v1/product-categories", json={"name": "Findings"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Silver clasp", "category_id": category["id"]}, headers=auth_headers
    ).json()

    quick = client.post(
        "/api/v1/receiving/quick-receive",
        json={
            "vendor_id": vendor["id"],
            "lines": [{"unresolved_item_description": "Bag of clasps", "received_quantity": 1, "received_unit_type": "bag"}],
        },
        headers=auth_headers,
    ).json()

    line_id = quick["receipt"]["lines"][0]["id"]
    resp = client.patch(
        f"/api/v1/receipt-lines/{line_id}/resolve", params={"product_id": product["id"]}, headers=auth_headers
    )
    assert resp.status_code == 200
    resolved_line = resp.json()["lines"][0]
    assert resolved_line["product_id"] == product["id"]
    assert resolved_line["receiving_status"] == "matched"
    # Once resolved, the line and its inventory unit should display the product's
    # name instead of the free-text description Patti typed in during receiving.
    assert resolved_line["product_name"] == "Silver clasp"
    assert resolved_line["unresolved_item_description"] is None

    inventory_unit_id = resolved_line["inventory_unit_id"]
    unit_resp = client.get(f"/api/v1/inventory-units/{inventory_unit_id}", headers=auth_headers)
    assert unit_resp.json()["product_name"] == "Silver clasp"
