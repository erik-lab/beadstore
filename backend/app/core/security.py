import uuid
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_keys import hash_api_key
from app.core.config import get_settings
from app.core.db import get_db
from app.models.api_client import ApiClient
from app.models.enums import ApiClientKind, ApiClientStatus
from app.models.profile import Profile

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Supabase projects migrated to the newer "JWT Signing Keys" system issue
# asymmetric-signed tokens (ES256/RS256), verified via the project's JWKS
# endpoint. Older/unmigrated projects (and our own test suite) still use a
# shared HS256 secret. We support both, keyed off the token's own "alg"
# header, and cache the JWKS client per JWKS URL (PyJWKClient itself caches
# fetched keys so this doesn't hit the network on every request).
_jwks_clients: dict[str, PyJWKClient] = {}


def _get_jwks_client() -> PyJWKClient:
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    client = _jwks_clients.get(jwks_url)
    if client is None:
        client = PyJWKClient(jwks_url)
        _jwks_clients[jwks_url] = client
    return client


class CurrentUser:
    def __init__(self, user_id: str, email: str | None):
        self.id = user_id
        self.email = email


def decode_supabase_jwt(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "HS256":
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.supabase_jwt_audience,
            )

        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience=settings.supabase_jwt_audience,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    except jwt.PyJWKClientError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_supabase_jwt(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")

    email = payload.get("email")
    user_uuid = uuid.UUID(user_id)

    profile = db.get(Profile, user_uuid)
    if profile is None:
        profile = Profile(id=user_uuid, email=email or "unknown@example.com")
        db.add(profile)
        try:
            db.commit()
        except IntegrityError:
            # Another concurrent request for the same first-time user created the
            # profile row first (e.g. two requests firing together on initial page
            # load). Discard our insert and use the row that won the race.
            db.rollback()
            profile = db.get(Profile, user_uuid)
    elif email and profile.email != email:
        profile.email = email
        db.commit()

    # Stamp this request's actor onto the session so the audit-trail flush
    # listener (app/models/audit_log.py) can attribute any writes made
    # later in this same request without threading a user param through
    # every router. Safe because `db` is cached per-request by FastAPI's
    # dependency injection — the same Session instance is handed to every
    # dependent, including the route handler's own `db` parameter.
    db.info["actor_id"] = user_uuid
    db.info["actor_email"] = profile.email

    return CurrentUser(user_id=user_id, email=profile.email)


# --- Non-human API credentials (storefront app, Etsy integration) ---------
# Parallel to CurrentUser/get_current_user above, but for callers that
# aren't a Supabase-authenticated staff login — see
# docs/design/api-tiers-work-plan.md. Not wired into any business router
# yet; only the /api-clients/whoami diagnostic endpoint uses it so far.


def get_api_client(
    api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> ApiClient:
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")

    client = db.query(ApiClient).filter(ApiClient.api_key_hash == hash_api_key(api_key)).first()
    if client is None or client.status != ApiClientStatus.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    client.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return client


def require_api_client_kind(kind: ApiClientKind):
    """Factory for scoping an endpoint to one face of the API, e.g.
    Depends(require_api_client_kind(ApiClientKind.storefront)) so a storefront
    key can't call an Etsy-only endpoint and vice versa.
    """

    def _check(client: ApiClient = Depends(get_api_client)) -> ApiClient:
        if client.kind != kind:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires an API client of kind '{kind.value}'",
            )
        return client

    return _check
