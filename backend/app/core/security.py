import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.profile import Profile

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

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

    return CurrentUser(user_id=user_id, email=profile.email)
