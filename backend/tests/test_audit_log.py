import json
import uuid

from app.models.location import Location


def test_create_and_update_are_captured_with_actor(client, auth_headers):
    created = client.post(
        "/api/v1/locations",
        json={"name": "Front Cabinet", "description": "Main display cabinet"},
        headers=auth_headers,
    ).json()

    resp = client.get(
        f"/api/v1/audit-logs?table_name=locations&record_id={created['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] == 1
    entry = page["items"][0]
    assert entry["action"] == "create"
    assert entry["actor_email"] == "patti@example.com"
    changes = json.loads(entry["changes"])
    assert changes["name"] == "Front Cabinet"

    client.patch(
        f"/api/v1/locations/{created['id']}",
        json={"description": "Back room shelving"},
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/v1/audit-logs?table_name=locations&record_id={created['id']}",
        headers=auth_headers,
    )
    page = resp.json()
    assert page["total"] == 2
    update_entry = next(e for e in page["items"] if e["action"] == "update")
    changes = json.loads(update_entry["changes"])
    assert changes["description"] == {"old": "Main display cabinet", "new": "Back room shelving"}


def test_created_by_and_updated_by_are_stamped(client, auth_headers, db_session):
    created = client.post(
        "/api/v1/locations",
        json={"name": "Back Room"},
        headers=auth_headers,
    ).json()
    location = db_session.get(Location, uuid.UUID(created["id"]))
    assert location.created_by is not None
    assert location.updated_by is not None
    assert location.created_by == location.updated_by


def test_audit_logs_scoped_to_requested_table_and_record(client, auth_headers):
    a = client.post("/api/v1/locations", json={"name": "Shelf A"}, headers=auth_headers).json()
    b = client.post("/api/v1/locations", json={"name": "Shelf B"}, headers=auth_headers).json()

    resp = client.get(
        f"/api/v1/audit-logs?table_name=locations&record_id={a['id']}",
        headers=auth_headers,
    )
    ids = {e["record_id"] for e in resp.json()["items"]}
    assert ids == {a["id"]}
    assert b["id"] not in ids


def test_list_audited_tables(client, auth_headers):
    client.post("/api/v1/locations", json={"name": "Shelf C"}, headers=auth_headers)

    resp = client.get("/api/v1/audit-logs/tables", headers=auth_headers)
    assert resp.status_code == 200
    assert "locations" in resp.json()
