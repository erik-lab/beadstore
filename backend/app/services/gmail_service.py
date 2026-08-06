"""Server-side Gmail OAuth + API calls for Order Email Scan.

Moved server-side (rather than the previous browser-only Google Identity
Services popup) specifically so the refresh token can be stored (encrypted)
and silently renewed — GIS's browser token client deliberately never hands
back a refresh token, so persisting credentials was impossible from the
browser alone. Requires a Google Cloud OAuth client of type "Web application"
(not just a JS origin) with GOOGLE_CLIENT_SECRET, since minting a refresh
token requires the server-side authorization_code exchange.
"""
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.email_match import match_reasons

settings = get_settings()

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"

SEARCH_WINDOW = "newer_than:180d"
MAX_MESSAGES = 60
# "in:inbox" keeps this from re-surfacing emails already filed into the
# orders label (or archived/other labels) by a prior Record Order run.
ORDER_QUERY = (
    f"in:inbox {SEARCH_WINDOW} "
    '(subject:order OR subject:confirmation OR subject:shipped OR subject:shipment '
    'OR subject:receipt OR subject:invoice OR subject:"thank you for your purchase")'
)

PARSEABLE_ATTACHMENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024


class GmailAuthError(Exception):
    """The refresh token was rejected — the account needs to be reconnected."""


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def build_authorize_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": f"{GMAIL_SCOPE} openid email",
        "access_type": "offline",
        # Forces Google to re-issue a refresh token even if this browser
        # already granted consent before (offline access tokens are only
        # handed back on the *first* consent otherwise).
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google rejected the sign-in. Please try connecting the account again.",
        )
    data = resp.json()
    if "refresh_token" not in data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google didn't grant offline access. Please try connecting the account again "
            "and accept the full permission request.",
        )
    return data


def refresh_access_token(refresh_token: str) -> str:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    if resp.status_code in (400, 401):
        raise GmailAuthError("Gmail refresh token was rejected.")
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not reach Gmail. Try again.")
    return resp.json()["access_token"]


def fetch_account_email(access_token: str) -> str:
    resp = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not read the Gmail account's own profile ({resp.status_code}). "
            "Please try connecting the account again.",
        )
    email = resp.json().get("email", "")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google didn't return an email address for this account.",
        )
    return email


def _get(access_token: str, path: str, params: dict | None = None) -> dict:
    resp = httpx.get(f"{GMAIL_API}{path}", headers={"Authorization": f"Bearer {access_token}"}, params=params, timeout=20)
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Gmail request failed ({resp.status_code}).")
    return resp.json() if resp.content else {}


def _post(access_token: str, path: str, body: dict) -> dict:
    resp = httpx.post(f"{GMAIL_API}{path}", headers={"Authorization": f"Bearer {access_token}"}, json=body, timeout=20)
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Gmail request failed ({resp.status_code}).")
    return resp.json() if resp.content else {}


def _header_value(headers: list[dict], name: str) -> str:
    return next((h.get("value", "") for h in headers if h.get("name", "").lower() == name.lower()), "")


def scan_inbox(access_token: str, vendor_names: list[str]) -> list[dict]:
    listing = _get(access_token, "/messages", params={"q": ORDER_QUERY, "maxResults": MAX_MESSAGES})
    ids = [m["id"] for m in listing.get("messages", [])]

    candidates = []
    for message_id in ids:
        msg = _get(
            access_token,
            f"/messages/{message_id}",
            params={
                "format": "metadata",
                "metadataHeaders": ["From", "Subject", "Date"],
            },
        )
        headers = (msg.get("payload") or {}).get("headers", [])
        from_address = _header_value(headers, "From")
        subject = _header_value(headers, "Subject")
        date = _header_value(headers, "Date")
        snippet = msg.get("snippet", "")
        reasons = match_reasons(from_address, subject, snippet, vendor_names)
        if reasons:
            candidates.append(
                {
                    "id": msg["id"],
                    "from_address": from_address,
                    "subject": subject,
                    "date": date,
                    "snippet": snippet,
                    "match_reasons": reasons,
                }
            )
    return candidates


def _collect_parts(part: dict, mime_type: str, found: list[str]) -> None:
    body = part.get("body") or {}
    if part.get("mimeType") == mime_type and body.get("data"):
        found.append(body["data"])
    for child in part.get("parts") or []:
        _collect_parts(child, mime_type, found)


def _decode_base64url_text(data: str) -> str:
    import base64

    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_body_text(payload: dict) -> str:
    plain: list[str] = []
    _collect_parts(payload, "text/plain", plain)
    if plain:
        return "\n".join(_decode_base64url_text(p) for p in plain).strip()

    html: list[str] = []
    _collect_parts(payload, "text/html", html)
    if html:
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
        extractor.feed("\n".join(_decode_base64url_text(h) for h in html))
        text = "".join(extractor.chunks)
        import re

        return re.sub(r"\n{3,}", "\n\n", text).strip()

    return ""


def _collect_attachment_refs(part: dict, found: list[dict]) -> None:
    body = part.get("body") or {}
    mime_type = part.get("mimeType")
    if (
        part.get("filename")
        and body.get("attachmentId")
        and mime_type in PARSEABLE_ATTACHMENT_TYPES
        and (body.get("size") or 0) <= MAX_ATTACHMENT_BYTES
    ):
        found.append(
            {
                "filename": part["filename"],
                "mime_type": mime_type,
                "attachment_id": body["attachmentId"],
            }
        )
    for child in part.get("parts") or []:
        _collect_attachment_refs(child, found)


def fetch_email_detail(access_token: str, message_id: str) -> dict:
    msg = _get(access_token, f"/messages/{message_id}", params={"format": "full"})
    payload = msg.get("payload") or {}
    headers = payload.get("headers", [])

    refs: list[dict] = []
    _collect_attachment_refs(payload, refs)
    attachments = []
    for ref in refs[:MAX_ATTACHMENTS]:
        data = _get(access_token, f"/messages/{message_id}/attachments/{ref['attachment_id']}")
        if data.get("data"):
            base64_std = data["data"].replace("-", "+").replace("_", "/")
            attachments.append({"filename": ref["filename"], "mime_type": ref["mime_type"], "base64_data": base64_std})

    return {
        "id": msg["id"],
        "from_address": _header_value(headers, "From"),
        "to_address": _header_value(headers, "To"),
        "subject": _header_value(headers, "Subject"),
        "date": _header_value(headers, "Date"),
        "body_text": _extract_body_text(payload) or msg.get("snippet", ""),
        "attachments": attachments,
    }


def _find_or_create_label(access_token: str, label_name: str) -> str:
    listing = _get(access_token, "/labels")
    existing = next((l for l in listing.get("labels", []) if l["name"] == label_name), None)
    if existing:
        return existing["id"]
    created = _post(access_token, "/labels", {"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"})
    return created["id"]


def move_to_orders_label(access_token: str, message_id: str, label_name: str) -> None:
    """Raises HTTPException(403) if the grant doesn't allow modify; caller
    (the router) turns that into the same permission-denied MoveEmailResult
    shape the old client-side code produced."""
    label_id = _find_or_create_label(access_token, label_name)
    resp = httpx.post(
        f"{GMAIL_API}/messages/{message_id}/modify",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"addLabelIds": [label_id], "removeLabelIds": ["INBOX"]},
        timeout=20,
    )
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission")
    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="error")
