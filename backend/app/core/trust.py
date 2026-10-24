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
import sys
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class TrustStoreStatus:
    """Whether the OS trust store was asked for, and whether it took effect.

    Carries `detail` because "requested but not active" has several causes
    that need different fixes, and reporting only a boolean sent me chasing
    the wrong one: a package installed under a *different* interpreter looks
    identical to one not installed at all.
    """

    requested: bool
    active: bool
    detail: str


_status = TrustStoreStatus(requested=False, active=False, detail="not requested")


def trust_store_status() -> TrustStoreStatus:
    return _status


def apply_system_trust_store() -> TrustStoreStatus:
    """Patch ssl to use the OS trust store.

    Must run before anything creates an SSL context, so callers invoke it at
    start-up rather than at the point of a request. Idempotent, since both
    the app and the maintenance scripts call it.
    """
    global _status

    if not settings.use_system_trust_store:
        _status = TrustStoreStatus(requested=False, active=False, detail="not requested")
        return _status
    if _status.active:
        return _status

    try:
        import truststore
    except ImportError as exc:
        # The interpreter running this is the one that needs the package, and
        # it is not necessarily the one `pip` resolves to — the same trap as
        # a `pip` outside the virtualenv. So name it.
        detail = (
            f"truststore could not be imported ({exc}). The interpreter that needs it is "
            f"{sys.executable} — check the package is installed for that one, not another "
            f"Python on the machine: \"{sys.executable}\" -m pip install truststore"
        )
        logger.warning("USE_SYSTEM_TRUST_STORE is on but %s", detail)
        _status = TrustStoreStatus(requested=True, active=False, detail=detail)
        return _status

    try:
        truststore.inject_into_ssl()
    except Exception as exc:  # noqa: BLE001 - truststore raises on unsupported platforms
        detail = f"truststore {getattr(truststore, '__version__', '?')} failed to install itself: {exc}"
        logger.warning("USE_SYSTEM_TRUST_STORE is on but %s", detail)
        _status = TrustStoreStatus(requested=True, active=False, detail=detail)
        return _status

    _status = TrustStoreStatus(
        requested=True,
        active=True,
        detail=f"verifying against the OS certificate store (truststore from {truststore.__file__})",
    )
    logger.info("Using the operating system's certificate store for TLS verification.")
    return _status
