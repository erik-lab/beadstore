"""Server-side Etsy OAuth (PKCE, mandatory per Etsy's docs) + Open API v3
calls. Same shape as gmail_service.py/outlook_service.py — a thin client
module, no state of its own. Every request goes to `settings.etsy_api_base_url`,
which points at the real Etsy API in production and at this same server's
built-in simulator (see app/etsy_simulator/) in local dev — the calling code
in etsy_sync_service.py doesn't know or care which.
"""
import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()

# Etsy's real OAuth authorize page isn't under /v3 like everything else —
# it's the shop-facing consent screen. The simulator mirrors this same
# split (oauth/connect + oauth/token) even though both live under one
# origin there, so the same relative paths work against either.
AUTHORIZE_PATH = "/oauth/connect"
TOKEN_PATH = "/v3/public/oauth/token"

# Split read/write scopes, per Etsy's v3 model — request only what push
# (listings_w) and pull (transactions_r) actually need. listings_r lets us
# read back a listing's current state to confirm a push landed.
REQUIRED_SCOPES = "listings_r listings_w transactions_r shops_r"


class EtsyAuthError(Exception):
    """The refresh token was rejected — the shop needs to be reconnected."""


def is_configured() -> bool:
    return bool(settings.etsy_client_id and settings.etsy_client_secret)


def generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return code_verifier, code_challenge


def build_authorize_url(redirect_uri: str, state: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.etsy_client_id,
        "redirect_uri": redirect_uri,
        "scope": REQUIRED_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{settings.etsy_api_base_url}{AUTHORIZE_PATH}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str, code_verifier: str) -> dict:
    resp = httpx.post(
        f"{settings.etsy_api_base_url}{TOKEN_PATH}",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.etsy_client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        },
        timeout=15,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Etsy rejected the sign-in. Please try connecting the shop again.",
        )
    data = resp.json()
    if "refresh_token" not in data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Etsy didn't return a refresh token.")
    return data


def refresh_access_token(refresh_token: str) -> str:
    resp = httpx.post(
        f"{settings.etsy_api_base_url}{TOKEN_PATH}",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.etsy_client_id,
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    if resp.status_code in (400, 401):
        raise EtsyAuthError("Etsy refresh token was rejected.")
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not reach Etsy. Try again.")
    return resp.json()["access_token"]


def _headers(access_token: str) -> dict:
    return {"x-api-key": settings.etsy_client_id, "Authorization": f"Bearer {access_token}"}


def get_shop(shop_id: str, access_token: str) -> dict:
    resp = httpx.get(f"{settings.etsy_api_base_url}/v3/application/shops/{shop_id}", headers=_headers(access_token), timeout=15)
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Etsy request failed ({resp.status_code}).")
    return resp.json()


def get_user_shops(user_id: str, access_token: str) -> list[dict]:
    # Etsy's access tokens are formatted "{user_id}.{opaque}" — the user_id
    # is how a newly-connected account's shop is discovered (there's no
    # "current shop" concept on the token itself). Assumes a single shop
    # per connected user, which matches Patti's actual setup.
    resp = httpx.get(
        f"{settings.etsy_api_base_url}/v3/application/users/{user_id}/shops",
        headers=_headers(access_token),
        timeout=15,
    )
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Etsy request failed ({resp.status_code}).")
    return resp.json().get("results", [])


def create_draft_listing(shop_id: str, access_token: str, payload: dict) -> dict:
    resp = httpx.post(
        f"{settings.etsy_api_base_url}/v3/application/shops/{shop_id}/listings",
        headers=_headers(access_token),
        json=payload,
        timeout=20,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Etsy rejected the listing ({resp.status_code}): {resp.text[:300]}",
        )
    return resp.json()


def update_listing_inventory(shop_id: str, listing_id: str, access_token: str, payload: dict) -> dict:
    resp = httpx.put(
        f"{settings.etsy_api_base_url}/v3/application/shops/{shop_id}/listings/{listing_id}/inventory",
        headers=_headers(access_token),
        json=payload,
        timeout=20,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Etsy rejected the inventory update ({resp.status_code}): {resp.text[:300]}",
        )
    return resp.json()


def get_shop_receipts(shop_id: str, access_token: str, min_created: int | None = None, limit: int = 25, offset: int = 0) -> dict:
    params = {"limit": limit, "offset": offset}
    if min_created is not None:
        params["min_created"] = min_created
    resp = httpx.get(
        f"{settings.etsy_api_base_url}/v3/application/shops/{shop_id}/receipts",
        headers=_headers(access_token),
        params=params,
        timeout=20,
    )
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Etsy request failed ({resp.status_code}).")
    return resp.json()


def simulate_sale(shop_id: str, listing_id: str, quantity: float, price: float | None) -> dict:
    """Seeds a fake paid order in the simulator so a "Pull Orders Now" click
    has something real to find -- see app/etsy_simulator's `/_simulator/seed-receipt`.
    Only meaningful when `settings.etsy_api_base_url` points at our own
    simulator; there is no such endpoint on the real Etsy API, so this
    would simply fail against production (guarded in the router before it
    gets here -- see routers/etsy.py).
    """
    resp = httpx.post(
        f"{settings.etsy_api_base_url}/_simulator/seed-receipt",
        json={"shop_id": shop_id, "listing_id": listing_id, "quantity": quantity, "price": price},
        timeout=15,
    )
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The simulator rejected the seed request.")
    return resp.json()
