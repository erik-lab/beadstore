import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import make_expired_token, make_token


def test_health_is_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_protected_route_requires_auth(client):
    resp = client.get("/api/v1/vendors")
    assert resp.status_code == 401


def test_me_creates_profile_on_first_login(client):
    token = make_token(email="erik@example.com")
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "erik@example.com"


def test_expired_token_is_rejected(client):
    token = make_expired_token()
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_invalid_token_is_rejected(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_concurrent_first_login_does_not_500(client, monkeypatch):
    """Two requests racing to auto-create the same first-time profile (e.g. React
    firing duplicate requests on initial mount) must not surface as a crash — the
    loser of the race should transparently pick up the row the winner created."""
    from app.models.profile import Profile

    user_id = str(uuid.uuid4())
    token = make_token(user_id=user_id, email="patti@example.com")

    original_commit = Session.commit
    calls = {"count": 0}

    def flaky_commit(self, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            # Simulate another request's concurrent insert winning the race.
            self.rollback()
            with_conflicting = Session(bind=self.get_bind())
            with_conflicting.add(Profile(id=uuid.UUID(user_id), email="patti@example.com"))
            with_conflicting.commit()
            with_conflicting.close()
            raise IntegrityError("insert", {}, Exception("UNIQUE constraint failed"))
        return original_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "patti@example.com"
