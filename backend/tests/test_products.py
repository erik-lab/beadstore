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
