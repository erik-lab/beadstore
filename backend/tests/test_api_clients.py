def test_create_api_client_returns_key_once(client, auth_headers):
    resp = client.post(
        "/api/v1/api-clients", json={"name": "Storefront App", "kind": "storefront"}, headers=auth_headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["api_key"].startswith("bsk_")
    assert body["kind"] == "storefront"
    assert body["status"] == "active"


def test_list_api_clients_does_not_leak_key_or_hash(client, auth_headers):
    client.post("/api/v1/api-clients", json={"name": "Etsy Integration", "kind": "etsy"}, headers=auth_headers)
    resp = client.get("/api/v1/api-clients", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json():
        assert "api_key" not in item
        assert "api_key_hash" not in item


def test_api_clients_require_staff_auth(client):
    resp = client.post("/api/v1/api-clients", json={"name": "X", "kind": "storefront"})
    assert resp.status_code == 401


def test_whoami_with_valid_key(client, auth_headers):
    created = client.post(
        "/api/v1/api-clients", json={"name": "Storefront App", "kind": "storefront"}, headers=auth_headers
    ).json()

    resp = client.get("/api/v1/api-access/whoami", headers={"X-API-Key": created["api_key"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["kind"] == "storefront"


def test_whoami_with_missing_key(client):
    resp = client.get("/api/v1/api-access/whoami")
    assert resp.status_code == 401


def test_whoami_with_bogus_key(client):
    resp = client.get("/api/v1/api-access/whoami", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 401


def test_whoami_rejects_revoked_key(client, auth_headers):
    created = client.post(
        "/api/v1/api-clients", json={"name": "Storefront App", "kind": "storefront"}, headers=auth_headers
    ).json()
    client.post(f"/api/v1/api-clients/{created['id']}/revoke", headers=auth_headers)

    resp = client.get("/api/v1/api-access/whoami", headers={"X-API-Key": created["api_key"]})
    assert resp.status_code == 401


def test_whoami_updates_last_used_at(client, auth_headers):
    created = client.post(
        "/api/v1/api-clients", json={"name": "Storefront App", "kind": "storefront"}, headers=auth_headers
    ).json()
    assert created["last_used_at"] is None

    client.get("/api/v1/api-access/whoami", headers={"X-API-Key": created["api_key"]})

    listed = client.get("/api/v1/api-clients", headers=auth_headers).json()
    refreshed = next(c for c in listed if c["id"] == created["id"])
    assert refreshed["last_used_at"] is not None
