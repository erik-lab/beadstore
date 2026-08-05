"""Encrypt-at-rest for stored OAuth refresh tokens, and a matching signer for
the short-lived CSRF state passed through the OAuth popup redirect — both
keyed off TOKEN_ENCRYPTION_KEY so only one secret needs to be provisioned.
"""
import base64
import hashlib
import hmac
import json
import time

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()

STATE_TTL_SECONDS = 10 * 60


def _fernet() -> Fernet:
    key = settings.token_encryption_key
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it as an environment variable."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise RuntimeError("Could not decrypt a stored token — TOKEN_ENCRYPTION_KEY may have changed.")


def _state_secret() -> bytes:
    # Derived from the same key rather than requiring a second secret env var.
    return hashlib.sha256(f"email-oauth-state:{settings.token_encryption_key}".encode()).digest()


def sign_oauth_state(provider: str) -> str:
    payload = json.dumps({"provider": provider, "exp": time.time() + STATE_TTL_SECONDS}).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(_state_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_oauth_state(state: str, expected_provider: str) -> None:
    try:
        payload_b64, signature = state.split(".", 1)
        expected_signature = hmac.new(_state_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("bad signature")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if payload.get("provider") != expected_provider:
            raise ValueError("provider mismatch")
        if payload.get("exp", 0) < time.time():
            raise ValueError("expired")
    except (ValueError, IndexError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This sign-in link expired or is invalid. Please try connecting the account again.",
        )
