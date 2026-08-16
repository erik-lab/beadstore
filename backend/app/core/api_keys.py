import hashlib
import secrets

# API keys are high-entropy random tokens (not user-chosen passwords), so a
# plain salted hash is standard practice here — no need for bcrypt/argon2's
# deliberate slowness, which exists to slow down guessing low-entropy
# secrets. A prefix makes a leaked key recognizable in logs at a glance
# (similar to how GitHub/Stripe prefix theirs) without revealing the secret.
_KEY_PREFIX = "bsk_"  # "beadstore key"


def generate_api_key() -> str:
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
