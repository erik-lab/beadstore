def _get_or_create_category(client, auth_headers, name):
    existing = client.get("/api/v1/product-categories", headers=auth_headers).json()
    match = next((c for c in existing if c["name"] == name), None)
    if match:
        return match
    return client.post("/api/v1/product-categories", json={"name": name}, headers=auth_headers).json()


def _setup_component(client, auth_headers, name="Round Bead 6mm", quantity=100, cost=0.10):
    category = _get_or_create_category(client, auth_headers, "Beads")
    product = client.post(
        "/api/v1/products", json={"name": name, "category_id": category["id"]}, headers=auth_headers
    ).json()
    inventory_unit = client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product["id"],
            "quantity": quantity,
            "unit_type": "count",
            "received_date": "2026-01-01",
            "cost_amount": cost,
        },
        headers=auth_headers,
    ).json()
    return product, inventory_unit


def _setup_piece_product(client, auth_headers, name="Beaded Bracelet"):
    category = _get_or_create_category(client, auth_headers, "Finished Jewelry")
    return client.post(
        "/api/v1/products",
        json={"name": name, "category_id": category["id"], "source_type": "assembled"},
        headers=auth_headers,
    ).json()


def test_product_defaults_to_purchased_source_type(client, auth_headers):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    product = client.post(
        "/api/v1/products", json={"name": "Amethyst Chip", "category_id": category["id"]}, headers=auth_headers
    ).json()
    assert product["source_type"] == "purchased"


def test_create_piece_with_no_components(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    resp = client.post(
        "/api/v1/piece-creations",
        json={"product_id": piece_product["id"], "created_date": "2026-02-01", "creation_cost": 12.50, "notes": "Made by hand"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["cost_source"] == "manual"
    assert body["creation_cost"] == 12.5
    assert body["components"] == []
    assert body["status"] == "active"

    inv = client.get(f"/api/v1/inventory-units?product_id={piece_product['id']}", headers=auth_headers).json()
    assert len(inv) == 1
    assert inv[0]["quantity"] == 1
    assert inv[0]["cost_amount"] == 12.5


def test_create_piece_estimates_cost_from_components(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    _, unit_a = _setup_component(client, auth_headers, name="Round Bead 6mm", quantity=100, cost=0.10)
    _, unit_b = _setup_component(client, auth_headers, name="Clasp", quantity=20, cost=1.50)

    resp = client.post(
        "/api/v1/piece-creations",
        json={
            "product_id": piece_product["id"],
            "created_date": "2026-02-01",
            "components": [
                {"inventory_unit_id": unit_a["id"], "quantity_used": 20},
                {"inventory_unit_id": unit_b["id"], "quantity_used": 1},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    # 20 * 0.10 + 1 * 1.50 = 3.50
    assert body["creation_cost"] == 3.5
    assert body["cost_source"] == "estimated_from_components"
    assert len(body["components"]) == 2

    unit_a_after = client.get(f"/api/v1/inventory-units/{unit_a['id']}", headers=auth_headers).json()
    assert unit_a_after["quantity"] == 80
    unit_b_after = client.get(f"/api/v1/inventory-units/{unit_b['id']}", headers=auth_headers).json()
    assert unit_b_after["quantity"] == 19


def test_manual_cost_overrides_component_estimate(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    _, unit = _setup_component(client, auth_headers, quantity=100, cost=0.10)

    resp = client.post(
        "/api/v1/piece-creations",
        json={
            "product_id": piece_product["id"],
            "creation_cost": 25.0,
            "components": [{"inventory_unit_id": unit["id"], "quantity_used": 10}],
        },
        headers=auth_headers,
    )
    body = resp.json()
    assert body["creation_cost"] == 25.0
    assert body["cost_source"] == "manual"


def test_component_quantity_exceeding_available_is_rejected(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    _, unit = _setup_component(client, auth_headers, quantity=5, cost=0.10)

    resp = client.post(
        "/api/v1/piece-creations",
        json={"product_id": piece_product["id"], "components": [{"inventory_unit_id": unit["id"], "quantity_used": 10}]},
        headers=auth_headers,
    )
    assert resp.status_code == 409

    # Nothing should have been consumed.
    unit_after = client.get(f"/api/v1/inventory-units/{unit['id']}", headers=auth_headers).json()
    assert unit_after["quantity"] == 5


def test_component_depleting_to_zero_marks_depleted(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    _, unit = _setup_component(client, auth_headers, quantity=10, cost=0.10)

    client.post(
        "/api/v1/piece-creations",
        json={"product_id": piece_product["id"], "components": [{"inventory_unit_id": unit["id"], "quantity_used": 10}]},
        headers=auth_headers,
    )
    unit_after = client.get(f"/api/v1/inventory-units/{unit['id']}", headers=auth_headers).json()
    assert unit_after["quantity"] == 0
    assert unit_after["status"] == "depleted"


def test_cost_left_blank_when_no_components_and_no_manual_cost(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    resp = client.post("/api/v1/piece-creations", json={"product_id": piece_product["id"]}, headers=auth_headers)
    body = resp.json()
    assert body["creation_cost"] is None


def test_cancel_restores_component_quantities(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    _, unit = _setup_component(client, auth_headers, quantity=50, cost=0.10)

    created = client.post(
        "/api/v1/piece-creations",
        json={"product_id": piece_product["id"], "components": [{"inventory_unit_id": unit["id"], "quantity_used": 20}]},
        headers=auth_headers,
    ).json()

    resp = client.post(f"/api/v1/piece-creations/{created['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    unit_after = client.get(f"/api/v1/inventory-units/{unit['id']}", headers=auth_headers).json()
    assert unit_after["quantity"] == 50

    resulting_unit = client.get(
        f"/api/v1/inventory-units/{created['resulting_inventory_unit_id']}", headers=auth_headers
    ).json()
    assert resulting_unit["quantity"] == 0
    assert resulting_unit["status"] == "archived"


def test_cancel_twice_is_rejected(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    created = client.post(
        "/api/v1/piece-creations", json={"product_id": piece_product["id"], "creation_cost": 5}, headers=auth_headers
    ).json()
    client.post(f"/api/v1/piece-creations/{created['id']}/cancel", headers=auth_headers)
    resp = client.post(f"/api/v1/piece-creations/{created['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 409


def test_cancel_refused_after_resulting_inventory_modified(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    created = client.post(
        "/api/v1/piece-creations", json={"product_id": piece_product["id"], "creation_cost": 5}, headers=auth_headers
    ).json()

    # Simulate the piece having since been sold/adjusted.
    client.post(
        f"/api/v1/inventory-units/{created['resulting_inventory_unit_id']}/adjustments",
        json={"adjustment_type": "manual_correction", "quantity_delta": -1, "reason": "sold"},
        headers=auth_headers,
    )

    resp = client.post(f"/api/v1/piece-creations/{created['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 409


def test_list_and_get_piece_creations(client, auth_headers):
    piece_product = _setup_piece_product(client, auth_headers)
    created = client.post(
        "/api/v1/piece-creations", json={"product_id": piece_product["id"], "creation_cost": 5}, headers=auth_headers
    ).json()

    listing = client.get("/api/v1/piece-creations", headers=auth_headers).json()
    assert any(pc["id"] == created["id"] for pc in listing)

    detail = client.get(f"/api/v1/piece-creations/{created['id']}", headers=auth_headers).json()
    assert detail["id"] == created["id"]
    assert detail["product_name"] == piece_product["name"]


def test_unknown_product_404s(client, auth_headers):
    resp = client.post(
        "/api/v1/piece-creations",
        json={"product_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_piece_creations_require_auth(client):
    resp = client.get("/api/v1/piece-creations")
    assert resp.status_code == 401
