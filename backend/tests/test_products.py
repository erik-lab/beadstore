def _create_category(client, auth_headers, name="Beads"):
    resp = client.post("/api/v1/product-categories", json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()


def test_create_and_get_product(client, auth_headers):
    category = _create_category(client, auth_headers)

    resp = client.post(
        "/api/v1/products",
        json={"name": "8mm Round Turquoise", "category_id": category["id"], "color": "Blue"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    product = resp.json()
    assert product["name"] == "8mm Round Turquoise"
    assert product["status"] == "active"

    resp = client.get(f"/api/v1/products/{product['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["color"] == "Blue"


def test_product_requires_name_and_category(client, auth_headers):
    resp = client.post("/api/v1/products", json={"name": "No category bead"}, headers=auth_headers)
    assert resp.status_code == 422


def test_product_archive_instead_of_delete(client, auth_headers):
    category = _create_category(client, auth_headers)
    resp = client.post(
        "/api/v1/products", json={"name": "Archivable bead", "category_id": category["id"]}, headers=auth_headers
    )
    product_id = resp.json()["id"]

    resp = client.post(f"/api/v1/products/{product_id}/archive", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    resp = client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_list_products_filter_by_category(client, auth_headers):
    beads = _create_category(client, auth_headers, "Beads")
    findings = _create_category(client, auth_headers, "Findings")
    client.post("/api/v1/products", json={"name": "Bead A", "category_id": beads["id"]}, headers=auth_headers)
    client.post("/api/v1/products", json={"name": "Finding A", "category_id": findings["id"]}, headers=auth_headers)

    resp = client.get(f"/api/v1/products?category_id={beads['id']}", headers=auth_headers)
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["Bead A"]


def test_inventory_unit_list_resolves_product_name(client, auth_headers):
    """List/detail views should show the product's name, not just its ID, so a user
    never has to guess what 'Linked product' refers to."""
    import datetime

    category = _create_category(client, auth_headers)
    product = client.post(
        "/api/v1/products",
        json={"name": "6mm Round Garnet", "category_id": category["id"], "sku": "GAR-6MM"},
        headers=auth_headers,
    ).json()

    client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product["id"],
            "quantity": 3,
            "unit_type": "strand",
            "received_date": str(datetime.date.today()),
        },
        headers=auth_headers,
    )

    resp = client.get(f"/api/v1/inventory-units?product_id={product['id']}", headers=auth_headers)
    assert resp.status_code == 200
    unit = resp.json()[0]
    assert unit["product_name"] == "6mm Round Garnet"
    assert unit["product_sku"] == "GAR-6MM"


def test_product_detail_shows_purchase_order_and_receipt_history(client, auth_headers):
    """Product detail page needs to answer 'which order/receipt did this come from' —
    covers the new /purchase-order-lines and /receipt-lines product sub-resources."""
    category = _create_category(client, auth_headers)
    product = client.post(
        "/api/v1/products", json={"name": "8mm Round Onyx", "category_id": category["id"]}, headers=auth_headers
    ).json()
    vendor = client.post("/api/v1/vendors", json={"name": "Stonecraft Supply"}, headers=auth_headers).json()

    po = client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": vendor["id"],
            "lines": [{"product_id": product["id"], "expected_quantity": 5, "expected_unit_type": "strand"}],
        },
        headers=auth_headers,
    ).json()
    line_id = po["lines"][0]["id"]

    client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "lines": [
                {
                    "purchase_order_line_id": line_id,
                    "product_id": product["id"],
                    "received_quantity": 5,
                    "received_unit_type": "strand",
                }
            ]
        },
        headers=auth_headers,
    )

    po_lines_resp = client.get(f"/api/v1/products/{product['id']}/purchase-order-lines", headers=auth_headers)
    assert po_lines_resp.status_code == 200
    po_lines = po_lines_resp.json()
    assert len(po_lines) == 1
    assert po_lines[0]["vendor_name"] == "Stonecraft Supply"
    assert po_lines[0]["purchase_order_id"] == po["id"]

    receipt_lines_resp = client.get(f"/api/v1/products/{product['id']}/receipt-lines", headers=auth_headers)
    assert receipt_lines_resp.status_code == 200
    receipt_lines = receipt_lines_resp.json()
    assert len(receipt_lines) == 1
    assert receipt_lines[0]["vendor_name"] == "Stonecraft Supply"
    assert receipt_lines[0]["receiving_status"] == "matched"


def test_product_resolves_category_and_subtype_names(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    subtype = client.post(
        "/api/v1/product-subtypes",
        json={"category_id": category["id"], "name": "Faceted"},
        headers=auth_headers,
    ).json()
    product = client.post(
        "/api/v1/products",
        json={"name": "6mm Faceted Bead", "category_id": category["id"], "subtype_id": subtype["id"]},
        headers=auth_headers,
    ).json()

    assert product["category_name"] == "Beads"
    assert product["subtype_name"] == "Faceted"

    resp = client.get("/api/v1/products", headers=auth_headers)
    listed = next(p for p in resp.json() if p["id"] == product["id"])
    assert listed["category_name"] == "Beads"
    assert listed["subtype_name"] == "Faceted"


def test_product_custom_subtype_used_when_no_formal_subtype(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products",
        json={"name": "Odd bead", "category_id": category["id"], "custom_subtype": "Irregular chip"},
        headers=auth_headers,
    ).json()

    assert product["subtype_id"] is None
    assert product["custom_subtype"] == "Irregular chip"
    assert product["subtype_name"] == "Irregular chip"


def test_rename_category_and_subtype(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    subtype = client.post(
        "/api/v1/product-subtypes",
        json={"category_id": category["id"], "name": "Round"},
        headers=auth_headers,
    ).json()

    resp = client.patch(f"/api/v1/product-categories/{category['id']}", json={"name": "Beads (Renamed)"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Beads (Renamed)"

    resp = client.patch(f"/api/v1/product-subtypes/{subtype['id']}", json={"name": "Round (Renamed)"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Round (Renamed)"


def test_attribute_options_returns_distinct_used_values(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    client.post(
        "/api/v1/products",
        json={"name": "Bead A", "category_id": category["id"], "color": "Blue"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/products",
        json={"name": "Bead B", "category_id": category["id"], "color": "Blue"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/products",
        json={"name": "Bead C", "category_id": category["id"], "color": "Green"},
        headers=auth_headers,
    )

    resp = client.get("/api/v1/products/attribute-options?field=color", headers=auth_headers)
    assert resp.status_code == 200
    assert sorted(resp.json()) == ["Blue", "Green"]


def test_attribute_options_rejects_unknown_field(client, auth_headers):
    resp = client.get("/api/v1/products/attribute-options?field=not_a_real_field", headers=auth_headers)
    assert resp.status_code == 400
