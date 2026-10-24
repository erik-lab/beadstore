"""Optionally use the operating system's certificate store.

On a machine where HTTPS is intercepted — corporate proxy, VPN, or antivirus
TLS scanning — the certificate Python is shown is signed by a locally
installed root. Browsers accept it because it's in the OS trust store;
Python doesn't, because it ships its own bundle. Every outbound call then
fails with CERTIFICATE_VERIFY_FAILED: Supabase Storage, the Anthropic calls
behind Import Inventory, Etsy later, and `pip` itself.

`truststore` makes Python's ssl module read the OS store instead, which fixes
all of them at once rather than per-library. pip has used it by default since
24.2.

Off unless `USE_SYSTEM_TRUST_STORE=true`, because a deployed server has no
interception to work around and should keep the predictable bundle. This is
never a way to skip verification — certificates are still verified, just
against the trust store the machine's own browser uses.
"""
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_applied = False


def apply_system_trust_store() -> bool:
    """Patch ssl to use the OS trust store. Returns whether it took effect.

    Must run before anything creates an SSL context, so callers invoke it at
    start-up rather than at the point of a request. Idempotent, since both
    the app and the maintenance scripts call it.
    """
    global _applied
    if not settings.use_system_trust_store or _applied:
        return _applied

    try:
        import truststore
    except ImportError:
        logger.warning(
            "USE_SYSTEM_TRUST_STORE is on but the truststore package isn't installed "
            "(pip install -r requirements.txt). Falling back to Python's own CA bundle."
        )
        return False

    truststore.inject_into_ssl()
    _applied = True
    logger.info("Using the operating system's certificate store for TLS verification.")
    return True
