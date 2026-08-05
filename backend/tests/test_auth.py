import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import make_expired_token, make_token


def test_health_is_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_supports_head(client):
    """Render's platform health check sends HEAD, not GET, before it will
    route any real traffic to the instance -- a 405 here made Render treat
    the whole service as unhealthy in production, well before browsers ever
    saw a real request."""
    resp = client.head("/health")
    assert resp.status_code == 200


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


def test_asymmetric_jwt_verified_via_jwks(client, monkeypatch):
    """Supabase projects migrated to 'JWT Signing Keys' issue ES256-signed tokens
    verified via the project's JWKS endpoint, instead of the legacy HS256 shared
    secret. The backend must support both, dispatching on the token's own 'alg'
    header."""
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.core import security

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": user_id,
            "email": "erik@example.com",
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
        },
        private_key,
        algorithm="ES256",
    )

    class FakeSigningKey:
        key = public_key

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    monkeypatch.setattr(security, "_get_jwks_client", lambda: FakeJWKClient())

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "erik@example.com"


def test_me_defaults_to_system_theme_and_no_avatar(client):
    token = make_token(email="erik@example.com")
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "system"
    assert body["avatar_data_url"] is None


def test_patch_me_updates_theme_and_avatar(client):
    token = make_token(email="erik@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/api/v1/auth/me", headers=headers)  # create the profile first

    resp = client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"theme": "dark", "avatar_data_url": "data:image/png;base64,abc123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "dark"
    assert body["avatar_data_url"] == "data:image/png;base64,abc123"

    # Persisted, not just echoed back.
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.json()["theme"] == "dark"
    assert resp.json()["avatar_data_url"] == "data:image/png;base64,abc123"


def test_patch_me_partial_update_leaves_other_fields_alone(client):
    token = make_token(email="erik@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/api/v1/auth/me", headers=headers)
    client.patch("/api/v1/auth/me", headers=headers, json={"theme": "light"})

    resp = client.patch(
        "/api/v1/auth/me", headers=headers, json={"avatar_data_url": "data:image/png;base64,zzz"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "light"
    assert body["avatar_data_url"] == "data:image/png;base64,zzz"


def test_patch_me_rejects_invalid_theme(client):
    token = make_token(email="erik@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/api/v1/auth/me", headers=headers)

    resp = client.patch("/api/v1/auth/me", headers=headers, json={"theme": "solarized"})
    assert resp.status_code == 422


def test_patch_me_requires_auth(client):
    resp = client.patch("/api/v1/auth/me", json={"theme": "dark"})
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
