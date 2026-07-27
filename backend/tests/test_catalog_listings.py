def _get_or_create_category(client, auth_headers, name="Beads"):
    resp = client.get("/api/v1/product-categories", headers=auth_headers)
    existing = next((c for c in resp.json() if c["name"] == name), None)
    if existing:
        return existing
    return client.post("/api/v1/product-categories", json={"name": name}, headers=auth_headers).json()


def _create_product(client, auth_headers, name="Test bead", description=None):
    category = _get_or_create_category(client, auth_headers)
    payload = {"name": name, "category_id": category["id"]}
    if description:
        payload["description"] = description
    return client.post("/api/v1/products", json=payload, headers=auth_headers).json()


def test_create_and_get_catalog_listing(client, auth_headers):
    product = _create_product(client, auth_headers)
    resp = client.post(
        "/api/v1/catalog-listings",
        json={"product_id": product["id"], "title": "8mm Round Turquoise Strand", "price": 12.5},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    listing = resp.json()
    assert listing["title"] == "8mm Round Turquoise Strand"
    assert listing["status"] == "draft"


def test_catalog_listing_resolves_product_name_and_description(client, auth_headers):
    product = _create_product(client, auth_headers, name="6mm Faceted Garnet", description="Deep red faceted beads")
    listing = client.post(
        "/api/v1/catalog-listings",
        json={"product_id": product["id"], "title": "Garnet Strand - Limited"},
        headers=auth_headers,
    ).json()

    assert listing["product_name"] == "6mm Faceted Garnet"
    assert listing["product_description"] == "Deep red faceted beads"

    resp = client.get("/api/v1/catalog-listings", headers=auth_headers)
    listed = next(item for item in resp.json() if item["id"] == listing["id"])
    assert listed["product_name"] == "6mm Faceted Garnet"


def test_catalog_listing_supports_expanded_attributes(client, auth_headers):
    product = _create_product(client, auth_headers, name="9mm Rose Quartz")
    category = _get_or_create_category(client, auth_headers, "Beads")

    resp = client.post(
        "/api/v1/catalog-listings",
        json={
            "product_id": product["id"],
            "title": "Rose Quartz Strand",
            "short_description": "Soft pink strand",
            "listing_description": "A full-length strand of polished rose quartz beads.",
            "price": 8.0,
            "status": "published",
            "sales_unit": "strand",
            "quantity_per_listing": 1,
            "available_quantity_mode": "derived_from_inventory",
            "category_override_id": category["id"],
            "subtype_override": "Polished",
            "tags": "pink,quartz,strand",
            "collection_theme": "Spring Collection",
            "featured": True,
            "sort_order": 5,
            "seo_title": "Rose Quartz Beaded Strand",
            "seo_description": "Shop rose quartz strands.",
            "listing_notes": "Reorder when below 5 strands.",
            "publish_readiness": "ready",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    listing = resp.json()
    assert listing["short_description"] == "Soft pink strand"
    assert listing["status"] == "published"
    assert listing["sales_unit"] == "strand"
    assert listing["available_quantity_mode"] == "derived_from_inventory"
    assert listing["category_override_name"] == "Beads"
    assert listing["subtype_override"] == "Polished"
    assert listing["tags"] == "pink,quartz,strand"
    assert listing["featured"] is True
    assert listing["sort_order"] == 5
    assert listing["publish_readiness"] == "ready"

    resp = client.patch(
        f"/api/v1/catalog-listings/{listing['id']}",
        json={"featured": False, "sort_order": 9},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["featured"] is False
    assert resp.json()["sort_order"] == 9


def test_catalog_listing_search_matches_title_or_product_name(client, auth_headers):
    product_a = _create_product(client, auth_headers, name="Turquoise Chip Bead")
    product_b = _create_product(client, auth_headers, name="Onyx Round Bead")
    client.post(
        "/api/v1/catalog-listings",
        json={"product_id": product_a["id"], "title": "Chip Strand Special"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/catalog-listings",
        json={"product_id": product_b["id"], "title": "Black Round Strand"},
        headers=auth_headers,
    )

    resp = client.get("/api/v1/catalog-listings?search=Turquoise", headers=auth_headers)
    titles = [item["title"] for item in resp.json()]
    assert titles == ["Chip Strand Special"]

    resp = client.get("/api/v1/catalog-listings?search=Special", headers=auth_headers)
    titles = [item["title"] for item in resp.json()]
    assert titles == ["Chip Strand Special"]
