import datetime


def _create_product(client, auth_headers, name="Test bead"):
    category = client.post("/api/v1/product-categories", json={"name": "Beads"}, headers=auth_headers).json()
    return client.post(
        "/api/v1/products", json={"name": name, "category_id": category["id"]}, headers=auth_headers
    ).json()


def _add_inventory(client, auth_headers, product_id, quantity):
    client.post(
        "/api/v1/inventory-units",
        json={
            "product_id": product_id,
            "quantity": quantity,
            "unit_type": "strand",
            "received_date": str(datetime.date.today()),
        },
        headers=auth_headers,
    )


def test_derived_availability_none_for_manual_mode(client, auth_headers):
    product = _create_product(client, auth_headers)
    listing = client.post(
        "/api/v1/catalog-listings",
        json={"product_id": product["id"], "title": "Listing", "available_quantity_mode": "manual"},
        headers=auth_headers,
    ).json()
    assert listing["derived_available_quantity"] is None


def test_derived_availability_sums_available_inventory(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 7)
    _add_inventory(client, auth_headers, product["id"], 3)

    listing = client.post(
        "/api/v1/catalog-listings",
        json={
            "product_id": product["id"],
            "title": "Listing",
            "available_quantity_mode": "derived_from_inventory",
        },
        headers=auth_headers,
    ).json()
    assert listing["derived_available_quantity"] == 10


def test_derived_availability_divides_by_quantity_per_listing(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 25)

    listing = client.post(
        "/api/v1/catalog-listings",
        json={
            "product_id": product["id"],
            "title": "Set of 10",
            "available_quantity_mode": "derived_from_inventory",
            "quantity_per_listing": 10,
        },
        headers=auth_headers,
    ).json()
    # floor(25 / 10) == 2 full sets sellable, not 2.5
    assert listing["derived_available_quantity"] == 2


def test_derived_availability_reflected_on_get_and_list(client, auth_headers):
    product = _create_product(client, auth_headers)
    _add_inventory(client, auth_headers, product["id"], 5)
    listing = client.post(
        "/api/v1/catalog-listings",
        json={
            "product_id": product["id"],
            "title": "Listing",
            "available_quantity_mode": "derived_from_inventory",
        },
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/v1/catalog-listings/{listing['id']}", headers=auth_headers)
    assert resp.json()["derived_available_quantity"] == 5

    resp = client.get("/api/v1/catalog-listings", headers=auth_headers)
    listed = next(item for item in resp.json() if item["id"] == listing["id"])
    assert listed["derived_available_quantity"] == 5
