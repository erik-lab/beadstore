def _setup_vendor_and_product(client, auth_headers):
    vendor = client.post("/api/v1/vendors", json={"name": "Sunrise Bead Supply"}, headers=auth_headers).json()
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "6mm Amethyst", "category_id": category["id"]}, headers=auth_headers
    ).json()
    return vendor, product


def _create_po(client, auth_headers, vendor_id, product_id, expected_quantity=10):
    return client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": vendor_id,
            "lines": [
                {
                    "product_id": product_id,
                    "expected_quantity": expected_quantity,
                    "expected_unit_type": "strand",
                }
            ],
        },
        headers=auth_headers,
    ).json()


def test_receive_full_match(client, auth_headers):
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"], expected_quantity=10)
    line_id = po["lines"][0]["id"]

    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"purchase_order_line_id": line_id, "product_id": product["id"], "received_quantity": 10, "received_unit_type": "strand"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["purchase_order_status"] == "received"
    assert result["summary"]["matched"] == 1

    inv = client.get(f"/api/v1/inventory-units?product_id={product['id']}", headers=auth_headers).json()
    assert len(inv) == 1
    assert inv[0]["quantity"] == 10


def test_receive_partial_shortage(client, auth_headers):
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"], expected_quantity=10)
    line_id = po["lines"][0]["id"]

    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"purchase_order_line_id": line_id, "product_id": product["id"], "received_quantity": 6, "received_unit_type": "strand"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["summary"]["shortage"] == 1
    assert result["purchase_order_status"] == "partially_received"

    po_after = client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth_headers).json()
    assert po_after["lines"][0]["status"] == "partially_received"


def test_receive_overage(client, auth_headers):
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"], expected_quantity=5)
    line_id = po["lines"][0]["id"]

    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"purchase_order_line_id": line_id, "product_id": product["id"], "received_quantity": 8, "received_unit_type": "strand"}]},
        headers=auth_headers,
    )
    assert resp.json()["summary"]["overage"] == 1


def test_receive_damaged_item_still_tracked(client, auth_headers):
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"], expected_quantity=5)
    line_id = po["lines"][0]["id"]

    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "lines": [
                {
                    "purchase_order_line_id": line_id,
                    "product_id": product["id"],
                    "received_quantity": 5,
                    "received_unit_type": "strand",
                    "receiving_status": "damaged",
                    "discrepancy_notes": "Box was crushed in transit",
                }
            ]
        },
        headers=auth_headers,
    )
    assert resp.json()["summary"]["damaged"] == 1
    inv = client.get(f"/api/v1/inventory-units?product_id={product['id']}", headers=auth_headers).json()
    assert inv[0]["status"] == "damaged"


def test_receive_unresolved_item(client, auth_headers):
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"], expected_quantity=5)

    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "lines": [
                {
                    "unresolved_item_description": "Unlabeled bag, not on order",
                    "received_quantity": 1,
                    "received_unit_type": "bag",
                }
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["summary"]["unresolved"] == 1

    unresolved = client.get("/api/v1/operations/unresolved-items", headers=auth_headers).json()
    assert len(unresolved) == 1


def test_multiple_receipts_against_same_order(client, auth_headers):
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"], expected_quantity=10)
    line_id = po["lines"][0]["id"]

    client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"purchase_order_line_id": line_id, "product_id": product["id"], "received_quantity": 4, "received_unit_type": "strand"}]},
        headers=auth_headers,
    )
    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"purchase_order_line_id": line_id, "product_id": product["id"], "received_quantity": 6, "received_unit_type": "strand"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    receipts = client.get(f"/api/v1/purchase-orders/{po['id']}/receipts", headers=auth_headers).json()
    assert len(receipts) == 2


def test_split_receipts_reconcile_cumulatively_to_received(client, auth_headers):
    """A line received across two partial receipts should reconcile against the cumulative
    total, not just the most recent receipt, and the order should reach 'received' once the
    full expected quantity has arrived across both receipts."""
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"], expected_quantity=10)
    line_id = po["lines"][0]["id"]

    first = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"purchase_order_line_id": line_id, "product_id": product["id"], "received_quantity": 6, "received_unit_type": "strand"}]},
        headers=auth_headers,
    ).json()
    assert first["purchase_order_status"] == "partially_received"
    assert first["summary"]["shortage"] == 1

    second = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"purchase_order_line_id": line_id, "product_id": product["id"], "received_quantity": 4, "received_unit_type": "strand"}]},
        headers=auth_headers,
    ).json()
    assert second["summary"]["matched"] == 1
    assert second["purchase_order_status"] == "received"

    po_after = client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth_headers).json()
    assert po_after["lines"][0]["status"] == "received"

    inv = client.get(f"/api/v1/inventory-units?product_id={product['id']}", headers=auth_headers).json()
    assert sum(u["quantity"] for u in inv) == 10


def test_cannot_receive_against_cancelled_order(client, auth_headers):
    vendor, product = _setup_vendor_and_product(client, auth_headers)
    po = _create_po(client, auth_headers, vendor["id"], product["id"])
    client.post(f"/api/v1/purchase-orders/{po['id']}/cancel", headers=auth_headers)

    resp = client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={"lines": [{"product_id": product["id"], "received_quantity": 1, "received_unit_type": "strand"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 409
