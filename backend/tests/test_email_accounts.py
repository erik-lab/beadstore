import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.core.crypto import sign_oauth_state
from app.models.enums import EmailAccountStatus
from app.services import gmail_service, outlook_service
from tests.conftest import make_token

settings = get_settings()


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "google_client_id", "test-google-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-google-secret")
    monkeypatch.setattr(settings, "microsoft_client_id", "test-ms-client-id")
    monkeypatch.setattr(settings, "microsoft_client_secret", "test-ms-secret")


def _connect_gmail_account(client, monkeypatch, email="orders@firemountaingems.com"):
    monkeypatch.setattr(
        gmail_service, "exchange_code_for_tokens", lambda code, redirect_uri: {"access_token": "at", "refresh_token": "rt"}
    )
    monkeypatch.setattr(gmail_service, "fetch_account_email", lambda access_token: email)
    state = sign_oauth_state("gmail")
    resp = client.get(f"/api/v1/email-accounts/gmail/callback?code=abc&state={state}")
    assert resp.status_code == 200
    return resp


def test_list_requires_auth(client):
    resp = client.get("/api/v1/email-accounts")
    assert resp.status_code == 401


def test_list_empty(client, auth_headers):
    resp = client.get("/api/v1/email-accounts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_connect_url_requires_configured(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "google_client_secret", "")
    resp = client.get("/api/v1/email-accounts/gmail/connect", headers=auth_headers)
    assert resp.status_code == 503


def test_connect_url_unknown_provider(client, auth_headers):
    resp = client.get("/api/v1/email-accounts/yahoo/connect", headers=auth_headers)
    assert resp.status_code == 404


def test_connect_url_returns_authorize_url(client, auth_headers):
    resp = client.get("/api/v1/email-accounts/gmail/connect", headers=auth_headers)
    assert resp.status_code == 200
    url = resp.json()["url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=test-google-client-id" in url
    assert "state=" in url


def test_oauth_callback_creates_account(client, monkeypatch):
    _connect_gmail_account(client, monkeypatch)
    token = make_token()
    resp = client.get("/api/v1/email-accounts", headers={"Authorization": f"Bearer {token}"})
    accounts = resp.json()
    assert len(accounts) == 1
    assert accounts[0]["provider"] == "gmail"
    assert accounts[0]["email_address"] == "orders@firemountaingems.com"
    assert accounts[0]["status"] == "active"
    # The refresh token must never be exposed via the API.
    assert "refresh_token" not in accounts[0]
    assert "refresh_token_encrypted" not in accounts[0]


def test_oauth_callback_rejects_bad_state(client):
    resp = client.get("/api/v1/email-accounts/gmail/callback?code=abc&state=garbage")
    assert resp.status_code == 400


def test_oauth_callback_rejects_state_for_wrong_provider(client):
    state = sign_oauth_state("outlook")
    resp = client.get(f"/api/v1/email-accounts/gmail/callback?code=abc&state={state}")
    assert resp.status_code == 400


def test_oauth_callback_handles_cancelled_consent(client):
    resp = client.get("/api/v1/email-accounts/gmail/callback?error=access_denied")
    assert resp.status_code == 200
    assert "cancelled" in resp.text.lower()


def test_oauth_callback_upserts_existing_account_by_email(client, monkeypatch, auth_headers):
    _connect_gmail_account(client, monkeypatch, email="orders@firemountaingems.com")
    _connect_gmail_account(client, monkeypatch, email="orders@firemountaingems.com")
    resp = client.get("/api/v1/email-accounts", headers=auth_headers)
    assert len(resp.json()) == 1


def test_delete_email_account(client, monkeypatch, auth_headers):
    _connect_gmail_account(client, monkeypatch)
    account_id = client.get("/api/v1/email-accounts", headers=auth_headers).json()[0]["id"]
    resp = client.delete(f"/api/v1/email-accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/v1/email-accounts", headers=auth_headers).json() == []


def test_delete_unknown_account_404s(client, auth_headers):
    resp = client.delete("/api/v1/email-accounts/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


def test_scan_account_returns_candidates(client, monkeypatch, auth_headers):
    _connect_gmail_account(client, monkeypatch)
    account_id = client.get("/api/v1/email-accounts", headers=auth_headers).json()[0]["id"]

    monkeypatch.setattr(gmail_service, "refresh_access_token", lambda refresh_token: "fresh-token")
    monkeypatch.setattr(
        gmail_service,
        "scan_inbox",
        lambda access_token, vendor_names: [
            {
                "id": "msg1",
                "from_address": "Fire Mountain Gems <orders@firemountaingems.com>",
                "subject": "Your bead order confirmation",
                "date": "Mon, 3 Aug 2026 10:00:00 -0700",
                "snippet": "shipped",
                "match_reasons": ["Mentions: bead"],
            }
        ],
    )
    resp = client.post(
        f"/api/v1/email-accounts/{account_id}/scan", headers=auth_headers, json={"vendor_names": ["Fire Mountain Gems"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == "msg1"
    assert body[0]["from_address"] == "Fire Mountain Gems <orders@firemountaingems.com>"


def test_scan_marks_needs_reauth_on_rejected_refresh_token(client, monkeypatch, auth_headers):
    _connect_gmail_account(client, monkeypatch)
    account_id = client.get("/api/v1/email-accounts", headers=auth_headers).json()[0]["id"]

    def _raise(refresh_token):
        raise gmail_service.GmailAuthError("rejected")

    monkeypatch.setattr(gmail_service, "refresh_access_token", _raise)
    resp = client.post(f"/api/v1/email-accounts/{account_id}/scan", headers=auth_headers, json={"vendor_names": []})
    assert resp.status_code == 409

    accounts = client.get("/api/v1/email-accounts", headers=auth_headers).json()
    assert accounts[0]["status"] == "needs_reauth"


def test_get_email_detail(client, monkeypatch, auth_headers):
    _connect_gmail_account(client, monkeypatch)
    account_id = client.get("/api/v1/email-accounts", headers=auth_headers).json()[0]["id"]

    monkeypatch.setattr(gmail_service, "refresh_access_token", lambda refresh_token: "fresh-token")
    monkeypatch.setattr(
        gmail_service,
        "fetch_email_detail",
        lambda access_token, message_id: {
            "id": message_id,
            "from_address": "vendor@example.com",
            "to_address": "me@example.com",
            "subject": "Order",
            "date": "Mon, 3 Aug 2026",
            "body_text": "Thanks for your order",
            "attachments": [],
        },
    )
    resp = client.get(f"/api/v1/email-accounts/{account_id}/emails/msg1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["body_text"] == "Thanks for your order"


def test_move_email_permission_denied(client, monkeypatch, auth_headers):
    from fastapi import HTTPException

    _connect_gmail_account(client, monkeypatch)
    account_id = client.get("/api/v1/email-accounts", headers=auth_headers).json()[0]["id"]

    monkeypatch.setattr(gmail_service, "refresh_access_token", lambda refresh_token: "fresh-token")

    def _raise_forbidden(access_token, message_id, label_name):
        raise HTTPException(status_code=403, detail="permission")

    monkeypatch.setattr(gmail_service, "move_to_orders_label", _raise_forbidden)
    resp = client.post(f"/api/v1/email-accounts/{account_id}/emails/msg1/move", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["moved"] is False
    assert body["reason"] == "permission"


def test_move_email_success(client, monkeypatch, auth_headers):
    _connect_gmail_account(client, monkeypatch)
    account_id = client.get("/api/v1/email-accounts", headers=auth_headers).json()[0]["id"]

    monkeypatch.setattr(gmail_service, "refresh_access_token", lambda refresh_token: "fresh-token")
    monkeypatch.setattr(gmail_service, "move_to_orders_label", lambda access_token, message_id, label_name: None)
    resp = client.post(f"/api/v1/email-accounts/{account_id}/emails/msg1/move", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"moved": True, "reason": None, "message": None}


def test_outlook_connect_and_scan(client, monkeypatch, auth_headers):
    monkeypatch.setattr(
        outlook_service,
        "exchange_code_for_tokens",
        lambda code, redirect_uri: {"access_token": "at", "refresh_token": "rt"},
    )
    monkeypatch.setattr(outlook_service, "fetch_account_email", lambda access_token: "orders@example.onmicrosoft.com")
    state = sign_oauth_state("outlook")
    resp = client.get(f"/api/v1/email-accounts/outlook/callback?code=abc&state={state}")
    assert resp.status_code == 200

    accounts = client.get("/api/v1/email-accounts", headers=auth_headers).json()
    assert len(accounts) == 1
    assert accounts[0]["provider"] == "outlook"

    monkeypatch.setattr(outlook_service, "refresh_access_token", lambda refresh_token: "fresh-token")
    monkeypatch.setattr(outlook_service, "scan_inbox", lambda access_token, vendor_names: [])
    resp = client.post(
        f"/api/v1/email-accounts/{accounts[0]['id']}/scan", headers=auth_headers, json={"vendor_names": []}
    )
    assert resp.status_code == 200
    assert resp.json() == []
