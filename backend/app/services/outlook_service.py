"""Server-side Microsoft OAuth + Graph API calls for Order Email Scan.

Moved server-side (rather than the previous browser-only MSAL.js popup) so
the refresh token can be stored (encrypted) and silently renewed — MSAL's
public-client (SPA) flow deliberately never exposes its refresh token to app
code, only using it internally for its own silent renewal, so persisting
credentials was impossible from the browser alone. Requires the Azure App
registration to also have a "Web" platform redirect URI (in addition to any
existing "Single-page application" one) with a client secret
(MICROSOFT_CLIENT_SECRET) configured under Certificates & secrets, since
minting a refresh token for a confidential client requires the server-side
authorization_code exchange.
"""
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.email_match import match_reasons

settings = get_settings()

# /organizations (not /common): this is a work/school mailbox connection
# only. Matches the authority used by the prior client-side MSAL flow.
TENANT = "organizations"
AUTH_URL = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
GRAPH_API = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/Mail.ReadWrite"
# User.Read is required for the /me call in fetch_account_email() below —
# most new app registrations get it by default, but that's not guaranteed
# (e.g. a registration that had its default permissions edited), so it's
# requested explicitly rather than assumed.
REQUEST_SCOPES = f"openid email offline_access https://graph.microsoft.com/User.Read {GRAPH_SCOPE}"

SEARCH_WINDOW_DAYS = 180
MAX_MESSAGES = 60

PARSEABLE_ATTACHMENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024


class OutlookAuthError(Exception):
    """The refresh token was rejected — the account needs to be reconnected."""


def is_configured() -> bool:
    return bool(settings.microsoft_client_id and settings.microsoft_client_secret)


def build_authorize_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": settings.microsoft_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "response_mode": "query",
        "scope": REQUEST_SCOPES,
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": REQUEST_SCOPES,
        },
        timeout=15,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Microsoft rejected the sign-in. Please try connecting the account again.",
        )
    data = resp.json()
    if "refresh_token" not in data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Microsoft didn't grant offline access. Please try connecting the account again.",
        )
    return data


def refresh_access_token(refresh_token: str) -> str:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "grant_type": "refresh_token",
            "scope": REQUEST_SCOPES,
        },
        timeout=15,
    )
    if resp.status_code in (400, 401):
        raise OutlookAuthError("Outlook refresh token was rejected.")
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not reach Outlook. Try again.")
    return resp.json()["access_token"]


def fetch_account_email(access_token: str) -> str:
    resp = httpx.get(f"{GRAPH_API}/me", headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not read the Outlook account's own profile ({resp.status_code}). "
            "Please try connecting the account again.",
        )
    data = resp.json()
    email = data.get("mail") or data.get("userPrincipalName") or ""
    if not email:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Microsoft didn't return an email address for this account.",
        )
    return email


def _get(access_token: str, path: str) -> dict:
    resp = httpx.get(f"{GRAPH_API}{path}", headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Outlook request failed ({resp.status_code}).")
    return resp.json() if resp.content else {}


def _post(access_token: str, path: str, body: dict) -> dict:
    resp = httpx.post(f"{GRAPH_API}{path}", headers={"Authorization": f"Bearer {access_token}"}, json=body, timeout=20)
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Outlook request failed ({resp.status_code}).")
    return resp.json() if resp.content else {}


def _format_from(from_field: dict | None) -> str:
    if not from_field or not from_field.get("emailAddress"):
        return ""
    address_info = from_field["emailAddress"]
    name = address_info.get("name")
    address = address_info.get("address")
    if name and address and name != address:
        return f"{name} <{address}>"
    return address or name or ""


def scan_inbox(access_token: str, vendor_names: list[str]) -> list[dict]:
    from datetime import datetime, timedelta, timezone

    since_iso = (datetime.now(timezone.utc) - timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "$filter": f"receivedDateTime ge {since_iso}",
        "$orderby": "receivedDateTime desc",
        "$top": str(MAX_MESSAGES),
        "$select": "id,subject,bodyPreview,receivedDateTime,from",
    }
    listing = _get(access_token, f"/me/mailFolders('inbox')/messages?{urlencode(params)}")

    candidates = []
    for msg in listing.get("value", []):
        from_address = _format_from(msg.get("from"))
        subject = msg.get("subject", "")
        snippet = msg.get("bodyPreview", "")
        reasons = match_reasons(from_address, subject, snippet, vendor_names)
        if reasons:
            candidates.append(
                {
                    "id": msg["id"],
                    "from_address": from_address,
                    "subject": subject,
                    "date": msg.get("receivedDateTime", ""),
                    "snippet": snippet,
                    "match_reasons": reasons,
                }
            )
    return candidates


def _html_to_text(html: str) -> str:
    import re
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.chunks: list[str] = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("style", "script"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("style", "script"):
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                self.chunks.append(data)

    extractor = _TextExtractor()
    extractor.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(extractor.chunks)).strip()


def fetch_email_detail(access_token: str, message_id: str) -> dict:
    msg = _get(
        access_token,
        f"/me/messages/{message_id}?$select=subject,from,toRecipients,receivedDateTime,body,hasAttachments",
    )

    body = msg.get("body") or {}
    body_content = body.get("content", "")
    body_text = _html_to_text(body_content) if body.get("contentType") == "html" else body_content.strip()

    attachments = []
    if msg.get("hasAttachments"):
        attachment_list = _get(access_token, f"/me/messages/{message_id}/attachments")
        for att in attachment_list.get("value", []):
            if len(attachments) >= MAX_ATTACHMENTS:
                break
            if (
                att.get("@odata.type") == "#microsoft.graph.fileAttachment"
                and att.get("contentType") in PARSEABLE_ATTACHMENT_TYPES
                and att.get("contentBytes")
                and (att.get("size") or 0) <= MAX_ATTACHMENT_BYTES
            ):
                attachments.append(
                    {"filename": att.get("name", "attachment"), "mime_type": att["contentType"], "base64_data": att["contentBytes"]}
                )

    to_recipients = msg.get("toRecipients") or []
    to_address = ", ".join(_format_from({"emailAddress": r.get("emailAddress")}) for r in to_recipients)

    return {
        "id": message_id,
        "from_address": _format_from(msg.get("from")),
        "to_address": to_address,
        "subject": msg.get("subject", ""),
        "date": msg.get("receivedDateTime", ""),
        "body_text": body_text,
        "attachments": attachments,
    }


def _find_or_create_folder(access_token: str, folder_name: str) -> str:
    escaped = folder_name.replace("'", "''")
    params = {"$filter": f"displayName eq '{escaped}'"}
    listing = _get(access_token, f"/me/mailFolders?{urlencode(params)}")
    existing = next(iter(listing.get("value", [])), None)
    if existing:
        return existing["id"]
    created = _post(access_token, "/me/mailFolders", {"displayName": folder_name})
    return created["id"]


def move_to_orders_folder(access_token: str, message_id: str, folder_name: str) -> None:
    """Raises HTTPException(403) if the grant doesn't allow move; caller
    (the router) turns that into the same permission-denied MoveEmailResult
    shape the old client-side code produced."""
    folder_id = _find_or_create_folder(access_token, folder_name)
    resp = httpx.post(
        f"{GRAPH_API}/me/messages/{message_id}/move",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"destinationId": folder_id},
        timeout=20,
    )
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission")
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="error")
