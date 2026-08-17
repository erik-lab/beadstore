"""A local stand-in for Etsy's real Open API v3 — close enough to their
actual request/response shapes (per their published docs) to exercise our
integration code (app/services/etsy_service.py, app/services/etsy_sync_service.py)
without live credentials, rate limits, or a real Etsy shop. Mounted only when
ETSY_SIMULATOR_ENABLED=true (see app/main.py) — never in production.

Endpoints under /v3/... and /oauth/... mirror Etsy's real paths/shapes.
Endpoints under /_simulator/... are simulator-only test helpers with no
Etsy equivalent — clearly namespaced so they're never mistaken for the real
thing.
"""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.etsy_simulator.state import ACCESS_TOKEN_TTL_SECONDS, AUTH_CODE_TTL_SECONDS, store

router = APIRouter(tags=["etsy-simulator"])

QPS_LIMIT = 10
QPD_LIMIT = 10_000


def _check_rate_limit(api_key: str):
    now = time.time()
    log = store.request_log.setdefault(api_key, [])
    log.append(now)
    # prune anything older than a day
    cutoff = now - 86400
    store.request_log[api_key] = [t for t in log if t > cutoff]
    log = store.request_log[api_key]

    if len(log) > QPD_LIMIT:
        raise HTTPException(status_code=429, detail="Queries Per Day limit exceeded", headers={"Retry-After": "3600"})
    last_second = [t for t in log if t > now - 1]
    if len(last_second) > QPS_LIMIT:
        raise HTTPException(status_code=429, detail="Queries Per Second limit exceeded", headers={"Retry-After": "1"})


def _require_api_key(x_api_key: str | None = Header(default=None)):
    settings = get_settings()
    if not x_api_key or x_api_key != settings.etsy_client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing x-api-key")
    _check_rate_limit(x_api_key)
    return x_api_key


def _require_access_token(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    store.prune_expired()
    entry = store.access_tokens.get(token)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    return entry


def _code_challenge_matches(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return secrets.compare_digest(computed, code_challenge)


# --- OAuth (mirrors https://www.etsy.com/oauth/connect and
# https://api.etsy.com/v3/public/oauth/token) ------------------------------


@router.get("/oauth/connect")
def oauth_connect(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
):
    # Real Etsy shows a consent screen here; the simulator auto-approves —
    # there's no human seller to click "allow" in an automated test/dev
    # environment, and the interesting part to exercise is the redirect
    # round-trip and the token exchange that follows, not a fake UI.
    if response_type != "code" or code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Unsupported response_type/code_challenge_method")
    code = secrets.token_urlsafe(24)
    store.auth_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "expires_at": time.time() + AUTH_CODE_TTL_SECONDS,
        "shop_id": next(iter(store.shops)),
    }
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}")


@router.post("/v3/public/oauth/token")
async def oauth_token(request: Request):
    # Parsed by hand rather than Starlette's request.form() — that requires
    # python-multipart installed even for a plain application/x-www-form-urlencoded
    # body (which is all Etsy's real token endpoint ever sends), and adding a
    # dependency just for that felt unnecessary.
    from urllib.parse import parse_qsl

    body = (await request.body()).decode()
    form = dict(parse_qsl(body))
    grant_type = form.get("grant_type")
    settings = get_settings()

    if form.get("client_id") != settings.etsy_client_id:
        raise HTTPException(status_code=401, detail="Invalid client_id")

    if grant_type == "authorization_code":
        code = form.get("code")
        code_verifier = form.get("code_verifier", "")
        entry = store.auth_codes.pop(code, None)
        if entry is None or entry["expires_at"] < time.time():
            raise HTTPException(status_code=400, detail="Invalid or expired authorization code")
        if entry["redirect_uri"] != form.get("redirect_uri"):
            raise HTTPException(status_code=400, detail="redirect_uri mismatch")
        if not _code_challenge_matches(code_verifier, entry["code_challenge"]):
            raise HTTPException(status_code=400, detail="PKCE verification failed")
        shop_id = entry["shop_id"]
        scope = entry["scope"]
    elif grant_type == "refresh_token":
        refresh_token = form.get("refresh_token")
        entry = store.refresh_tokens.get(refresh_token)
        if entry is None:
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        shop_id = entry["shop_id"]
        scope = entry["scope"]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type '{grant_type}'")

    access_token = f"{shop_id}.{secrets.token_urlsafe(24)}"
    refresh_token = f"{shop_id}.{secrets.token_urlsafe(24)}"
    store.access_tokens[access_token] = {"shop_id": shop_id, "scope": scope, "expires_at": time.time() + ACCESS_TOKEN_TTL_SECONDS}
    store.refresh_tokens[refresh_token] = {"shop_id": shop_id, "scope": scope}

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "refresh_token": refresh_token,
    }


# --- Application API (mirrors /v3/application/...) ------------------------


@router.get("/v3/application/shops/{shop_id}")
def get_shop(shop_id: str, api_key: str = Depends(_require_api_key)):
    shop = store.shops.get(shop_id)
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


@router.get("/v3/application/users/{user_id}/shops")
def get_user_shops(user_id: str, token: dict = Depends(_require_access_token), api_key: str = Depends(_require_api_key)):
    # Real Etsy's access_token embeds the user_id this way; the simulator's
    # tokens are minted per-shop already (see oauth_token above), so the
    # "user_id" a caller passes here is really the shop_id it was issued
    # for — close enough to exercise the discovery call shape without
    # modeling Etsy's separate user/shop identity split.
    shop = store.shops.get(user_id)
    if shop is None or token["shop_id"] != user_id:
        return {"count": 0, "results": []}
    return {"count": 1, "results": [shop]}


@router.post("/v3/application/shops/{shop_id}/listings", status_code=201)
async def create_draft_listing(
    shop_id: str,
    request: Request,
    token: dict = Depends(_require_access_token),
    api_key: str = Depends(_require_api_key),
):
    if token["shop_id"] != shop_id:
        raise HTTPException(status_code=403, detail="Token is not authorized for this shop")
    if "listings_w" not in token["scope"].split():
        raise HTTPException(status_code=403, detail="Missing required scope: listings_w")

    body = await request.json()
    listing_id = store.next_listing_id()
    listing = {
        "listing_id": listing_id,
        "shop_id": shop_id,
        "state": "draft",
        "title": body.get("title"),
        "description": body.get("description"),
        "price": body.get("price"),
        "quantity": body.get("quantity"),
        "taxonomy_id": body.get("taxonomy_id"),
        "who_made": body.get("who_made"),
        "when_made": body.get("when_made"),
        "shipping_profile_id": body.get("shipping_profile_id"),
        "return_policy_id": body.get("return_policy_id"),
        "is_supply": body.get("is_supply", False),
    }
    store.listings[listing_id] = listing
    return listing


@router.put("/v3/application/shops/{shop_id}/listings/{listing_id}/inventory")
async def update_listing_inventory(
    shop_id: str,
    listing_id: str,
    request: Request,
    token: dict = Depends(_require_access_token),
    api_key: str = Depends(_require_api_key),
):
    if token["shop_id"] != shop_id:
        raise HTTPException(status_code=403, detail="Token is not authorized for this shop")
    if "listings_w" not in token["scope"].split():
        raise HTTPException(status_code=403, detail="Missing required scope: listings_w")
    listing = store.listings.get(listing_id)
    if listing is None or listing["shop_id"] != shop_id:
        raise HTTPException(status_code=404, detail="Listing not found")

    body = await request.json()
    listing["products"] = body.get("products", [])
    return {"listing_id": listing_id, "products": listing["products"]}


@router.get("/v3/application/shops/{shop_id}/receipts")
def get_shop_receipts(
    shop_id: str,
    min_created: int | None = None,
    limit: int = 25,
    offset: int = 0,
    token: dict = Depends(_require_access_token),
    api_key: str = Depends(_require_api_key),
):
    if token["shop_id"] != shop_id:
        raise HTTPException(status_code=403, detail="Token is not authorized for this shop")
    if "transactions_r" not in token["scope"].split():
        raise HTTPException(status_code=403, detail="Missing required scope: transactions_r")

    results = [r for r in store.receipts.values() if r["shop_id"] == shop_id]
    if min_created is not None:
        results = [r for r in results if r["created_timestamp"] >= min_created]
    results.sort(key=lambda r: r["created_timestamp"])
    page = results[offset : offset + limit]
    return {"count": len(results), "results": page}


# --- Simulator-only test helpers — no Etsy equivalent ----------------------


@router.post("/_simulator/reset")
def simulator_reset():
    store.reset()
    return {"ok": True}


@router.post("/_simulator/seed-receipt")
def simulator_seed_receipt(payload: dict = Body(...)):
    """Inject a fake paid order, since there's no real buyer flow to trigger
    one. `payload`: {shop_id, listing_id, quantity, price}.
    """
    shop_id = payload.get("shop_id") or next(iter(store.shops))
    receipt_id = store.next_receipt_id()
    transaction_id = store.next_transaction_id()
    receipt = {
        "receipt_id": receipt_id,
        "shop_id": shop_id,
        "created_timestamp": int(time.time()),
        "status": "Paid",
        "transactions": [
            {
                "transaction_id": transaction_id,
                "listing_id": payload["listing_id"],
                "quantity": payload.get("quantity", 1),
                "price": {"amount": int(float(payload.get("price", 0)) * 100), "divisor": 100, "currency_code": "USD"},
            }
        ],
    }
    store.receipts[receipt_id] = receipt
    return receipt


@router.post("/_simulator/trigger-webhook")
async def simulator_trigger_webhook(payload: dict = Body(...)):
    """Fire a fake order.paid webhook at our own receiver, signed the same
    way a real Etsy webhook would be — exercises the receiver's signature
    verification, not just the simulator's own data.
    """
    import hmac as hmac_lib
    import json

    import httpx

    settings = get_settings()
    receipt_id = payload["receipt_id"]
    body = json.dumps({"event_type": "order.paid", "receipt_id": receipt_id}).encode()
    signature = hmac_lib.new(settings.etsy_webhook_signing_secret.encode(), body, hashlib.sha256).hexdigest()

    target = payload.get("target_url", "http://localhost:8000/api/v1/etsy/webhook")
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.post(target, content=body, headers={"X-Etsy-Signature": signature, "Content-Type": "application/json"})
    return {"delivered_status": resp.status_code}
