def test_create_and_list_hints(client, auth_headers):
    resp = client.post(
        "/api/v1/hints",
        json={"page": "dashboard", "item_key": "active_products", "text": "How many active products."},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    hint = resp.json()
    assert hint["page"] == "dashboard"

    resp = client.get("/api/v1/hints?page=dashboard", headers=auth_headers)
    assert resp.status_code == 200
    assert any(h["item_key"] == "active_products" for h in resp.json())


def test_duplicate_page_item_key_conflicts(client, auth_headers):
    payload = {"page": "dashboard", "item_key": "open_orders", "text": "Open orders."}
    resp = client.post("/api/v1/hints", json=payload, headers=auth_headers)
    assert resp.status_code == 201

    resp = client.post("/api/v1/hints", json=payload, headers=auth_headers)
    assert resp.status_code == 409


def test_update_hint_text(client, auth_headers):
    created = client.post(
        "/api/v1/hints",
        json={"page": "products", "item_key": "category", "text": "Original text."},
        headers=auth_headers,
    ).json()

    resp = client.patch(f"/api/v1/hints/{created['id']}", json={"text": "Updated text."}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["text"] == "Updated text."


def test_delete_hint(client, auth_headers):
    created = client.post(
        "/api/v1/hints",
        json={"page": "products", "item_key": "sku", "text": "SKU hint."},
        headers=auth_headers,
    ).json()

    resp = client.delete(f"/api/v1/hints/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get("/api/v1/hints?page=products", headers=auth_headers)
    assert all(h["id"] != created["id"] for h in resp.json())


def test_hints_require_auth(client):
    resp = client.get("/api/v1/hints")
    assert resp.status_code == 401
