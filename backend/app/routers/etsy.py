"""Connecting and syncing with an Etsy shop — see
docs/design/api-tiers-work-plan.md Phase 3. Same server-mediated OAuth
pattern as app/routers/email_accounts.py (full-navigation popup callback,
refresh token encrypted at rest), plus PKCE (mandatory on every Etsy
authorization request) and the push/pull sync endpoints.
"""
import hashlib
import hmac
import html as html_lib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt_token, encrypt_token, sign_oauth_state, verify_oauth_state
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.enums import EtsyAccountStatus
from app.models.etsy_account import EtsyAccount
from app.models.etsy_listing_sync import EtsyListingSync
from app.schemas.etsy import (
    EtsyAccountRead,
    EtsyConnectUrlResponse,
    EtsyListingSyncRead,
    EtsyPullResult,
    EtsyPushRequest,
    EtsySimulateSaleRequest,
)
from app.services import etsy_service, etsy_sync_service

router = APIRouter(prefix="/etsy", tags=["etsy"])
settings = get_settings()


def _redirect_uri(request: Request) -> str:
    # Same reasoning as email_accounts._redirect_uri: don't trust
    # request.url.scheme behind Render's TLS-terminating proxy.
    host = request.url.hostname or ""
    scheme = "http" if host in ("localhost", "127.0.0.1") else "https"
    port = request.url.port
    netloc = f"{host}:{port}" if port and scheme == "http" else host
    return f"{scheme}://{netloc}/api/v1/etsy/callback"


def _callback_page(status_label: str, message: str, ok: bool) -> HTMLResponse:
    payload = json.dumps({"source": "patti-etsy-connect", "ok": ok, "message": message})
    safe_status = html_lib.escape(status_label)
    safe_message = html_lib.escape(message)
    close_script = "window.close();" if ok else ""
    close_button = "" if ok else '<button onclick="window.close()">Close window</button>'
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{safe_status}</title></head>
<body style="font: 15px system-ui, sans-serif; padding: 32px; color: #16131c;">
<h2>{safe_status}</h2>
<p>{safe_message}</p>
{close_button}
<script>
  if (window.opener) {{
    window.opener.postMessage({payload}, window.location.origin);
  }}
  {close_script}
</script>
</body></html>"""
    return HTMLResponse(content=html)


@router.get("/accounts", response_model=list[EtsyAccountRead], dependencies=[Depends(get_current_user)])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(EtsyAccount).order_by(EtsyAccount.created_at).all()


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_user)])
def delete_account(account_id: uuid.UUID, db: Session = Depends(get_db)):
    account = db.get(EtsyAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etsy account not found")
    db.delete(account)
    db.commit()


@router.get("/connect", response_model=EtsyConnectUrlResponse, dependencies=[Depends(get_current_user)])
def get_connect_url(request: Request):
    if not etsy_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Etsy isn't configured on the server yet."
        )
    code_verifier, code_challenge = etsy_service.generate_pkce_pair()
    # code_verifier rides in the signed state (see core/crypto.py) rather
    # than a server-side session — nothing secret from the browser's own
    # perspective (it's the party that generated it), the signature just
    # stops it being swapped for a different one in transit.
    state = sign_oauth_state("etsy", extra={"code_verifier": code_verifier})
    url = etsy_service.build_authorize_url(_redirect_uri(request), state, code_challenge)
    return EtsyConnectUrlResponse(url=url)


@router.get("/callback", include_in_schema=False)
def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error or not code or not state:
        return _callback_page("Sign-in cancelled", "Sign-in was cancelled or denied. You can close this window.", ok=False)

    try:
        state_payload = verify_oauth_state(state, "etsy")
        tokens = etsy_service.exchange_code_for_tokens(code, _redirect_uri(request), state_payload["code_verifier"])
        user_id = tokens["access_token"].split(".", 1)[0]
        shops = etsy_service.get_user_shops(user_id, tokens["access_token"])
        if not shops:
            return _callback_page("Connection failed", "This Etsy account has no shop to connect.", ok=False)
        shop_info = shops[0]

        shop_id = str(shop_info["shop_id"])
        existing = db.query(EtsyAccount).filter(EtsyAccount.shop_id == shop_id).first()
        encrypted = encrypt_token(tokens["refresh_token"])
        if existing:
            existing.refresh_token_encrypted = encrypted
            existing.status = EtsyAccountStatus.active
            existing.shop_name = shop_info.get("shop_name")
        else:
            db.add(
                EtsyAccount(
                    shop_id=shop_id,
                    shop_name=shop_info.get("shop_name"),
                    refresh_token_encrypted=encrypted,
                    scopes=etsy_service.REQUIRED_SCOPES,
                )
            )
        db.commit()
    except HTTPException as exc:
        return _callback_page("Connection failed", str(exc.detail), ok=False)
    except RuntimeError as exc:
        # e.g. TOKEN_ENCRYPTION_KEY not set — surfaced here instead of a bare 500.
        return _callback_page("Connection failed", str(exc), ok=False)

    return _callback_page("Etsy shop connected", "You can close this window.", ok=True)


@router.post("/listings/{catalog_listing_id}/push", response_model=EtsyListingSyncRead, dependencies=[Depends(get_current_user)])
def push_listing(catalog_listing_id: uuid.UUID, payload: EtsyPushRequest, db: Session = Depends(get_db)):
    overrides = payload.model_dump(exclude_unset=True)
    return etsy_sync_service.push_listing(db, catalog_listing_id, overrides)


@router.get(
    "/listings/{catalog_listing_id}/sync", response_model=EtsyListingSyncRead, dependencies=[Depends(get_current_user)]
)
def get_listing_sync(catalog_listing_id: uuid.UUID, db: Session = Depends(get_db)):
    row = db.query(EtsyListingSync).filter(EtsyListingSync.catalog_listing_id == catalog_listing_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This listing has never been pushed to Etsy.")
    return row


@router.post("/pull", response_model=EtsyPullResult, dependencies=[Depends(get_current_user)])
def pull_receipts(db: Session = Depends(get_db)):
    return etsy_sync_service.pull_receipts(db)


@router.post("/simulate-sale", dependencies=[Depends(get_current_user)])
def simulate_sale(payload: EtsySimulateSaleRequest, db: Session = Depends(get_db)):
    # Play button for the simulator, not a real Etsy capability — there's no
    # "make a fake sale happen" endpoint on the real API, so this only ever
    # works when ETSY_SIMULATOR_ENABLED is on (which is exactly when a real
    # shop isn't connected to anything that could be confused for one).
    if not settings.etsy_simulator_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Etsy simulator isn't enabled on this server, so there's nothing to simulate a sale against.",
        )
    sync_row = (
        db.query(EtsyListingSync).filter(EtsyListingSync.catalog_listing_id == payload.catalog_listing_id).first()
    )
    if sync_row is None or sync_row.etsy_listing_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Push this listing to Etsy before simulating a sale for it.",
        )
    price = payload.price if payload.price is not None else float(sync_row.catalog_listing.price or 0)
    return etsy_service.simulate_sale(sync_row.etsy_shop_id, sync_row.etsy_listing_id, payload.quantity, price)


@router.post("/webhook", include_in_schema=False)
async def etsy_webhook(request: Request, db: Session = Depends(get_db)):
    # No get_current_user here — Etsy itself calls this, authenticated by
    # signature instead. A broad reconciliation pull rather than fetching
    # the one receipt named in the payload: idempotent (dedupes against
    # Sale.external_order_id already), and self-healing if an earlier
    # webhook was ever missed, at the cost of one extra Etsy API call per
    # delivery — an acceptable trade against the complexity of a
    # single-receipt fetch path used nowhere else.
    body = await request.body()
    signature = request.headers.get("X-Etsy-Signature", "")
    expected = hmac.new(settings.etsy_webhook_signing_secret.encode(), body, hashlib.sha256).hexdigest()
    if not settings.etsy_webhook_signing_secret or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    result = etsy_sync_service.pull_receipts(db)
    return {"ok": True, **result}
