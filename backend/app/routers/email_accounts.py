"""Connected mailboxes (Gmail/Outlook) for Order Email Scan.

Server-mediated OAuth: the popup navigates directly between the provider's
consent screen and our own /callback route (a full top-level navigation, not
a fetch — so it carries no Authorization header and isn't behind
get_current_user), which exchanges the code for a refresh token, encrypts
it, and stores/updates the EmailAccount row. Every other endpoint here is
authenticated and mints a fresh access token from the stored refresh token
right before use — access tokens are never persisted.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt_token, encrypt_token, sign_oauth_state, verify_oauth_state
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.email_account import EmailAccount
from app.models.enums import EmailAccountStatus, EmailProvider
from app.schemas.email_account import (
    CandidateEmailOut,
    ConnectUrlResponse,
    EmailAccountRead,
    EmailDetailOut,
    MoveEmailResult,
    ScanRequest,
)
from app.services import gmail_service, outlook_service

router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])
settings = get_settings()

_SERVICES = {EmailProvider.gmail: gmail_service, EmailProvider.outlook: outlook_service}
_ORDERS_LABEL_SETTING = {
    EmailProvider.gmail: lambda s: s.gmail_orders_label,
    EmailProvider.outlook: lambda s: s.outlook_orders_label,
}


def _provider(provider_str: str) -> EmailProvider:
    try:
        return EmailProvider(provider_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown email provider.")


def _redirect_uri(request: Request, provider: EmailProvider) -> str:
    # Deliberately not trusting request.url.scheme: Render terminates TLS in
    # front of this service, so an unproxied scheme read reports "http" even
    # in production, which Google/Microsoft reject for non-localhost redirect
    # URIs. Local dev is always plain http on localhost/127.0.0.1.
    host = request.url.hostname or ""
    scheme = "http" if host in ("localhost", "127.0.0.1") else "https"
    port = request.url.port
    netloc = f"{host}:{port}" if port and scheme == "http" else host
    return f"{scheme}://{netloc}/api/v1/email-accounts/{provider.value}/callback"


def _get_account(account_id: uuid.UUID, db: Session) -> EmailAccount:
    account = db.get(EmailAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email account not found.")
    return account


def _ensure_access_token(account: EmailAccount, db: Session) -> str:
    service = _SERVICES[account.provider]
    refresh_token = decrypt_token(account.refresh_token_encrypted)
    try:
        return service.refresh_access_token(refresh_token)
    except (gmail_service.GmailAuthError, outlook_service.OutlookAuthError):
        account.status = EmailAccountStatus.needs_reauth
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{account.provider.value.title()} access for {account.email_address} has expired. "
            "Reconnect this account to keep scanning it.",
        )


@router.get("", response_model=list[EmailAccountRead], dependencies=[Depends(get_current_user)])
def list_email_accounts(db: Session = Depends(get_db)):
    return db.query(EmailAccount).order_by(EmailAccount.created_at).all()


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_user)])
def delete_email_account(account_id: uuid.UUID, db: Session = Depends(get_db)):
    account = _get_account(account_id, db)
    db.delete(account)
    db.commit()


@router.get("/{provider}/connect", response_model=ConnectUrlResponse, dependencies=[Depends(get_current_user)])
def get_connect_url(provider: str, request: Request):
    provider_enum = _provider(provider)
    service = _SERVICES[provider_enum]
    if not service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{provider_enum.value.title()} isn't configured on the server yet.",
        )
    state = sign_oauth_state(provider_enum.value)
    url = service.build_authorize_url(_redirect_uri(request, provider_enum), state)
    return ConnectUrlResponse(url=url)


def _callback_page(status_label: str, message: str) -> HTMLResponse:
    # Rendered inside the popup window itself (this is where the provider's
    # own redirect lands) — never part of the React app. Tells the opener
    # window it can refresh its account list, then closes itself.
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{status_label}</title></head>
<body style="font: 15px system-ui, sans-serif; padding: 32px; color: #16131c;">
<p>{message}</p>
<p>You can close this window if it doesn't close automatically.</p>
<script>
  if (window.opener) {{
    window.opener.postMessage({{ source: "patti-email-account-connect" }}, window.location.origin);
  }}
  window.close();
</script>
</body></html>"""
    return HTMLResponse(content=html)


@router.get("/{provider}/callback", include_in_schema=False)
def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    provider_enum = _provider(provider)
    if error or not code or not state:
        return _callback_page("Sign-in cancelled", "Sign-in was cancelled or denied. You can close this window.")

    verify_oauth_state(state, provider_enum.value)
    service = _SERVICES[provider_enum]
    redirect_uri = _redirect_uri(request, provider_enum)

    try:
        tokens = service.exchange_code_for_tokens(code, redirect_uri)
        email_address = service.fetch_account_email(tokens["access_token"])

        existing = (
            db.query(EmailAccount)
            .filter(EmailAccount.provider == provider_enum, EmailAccount.email_address == email_address)
            .first()
        )
        encrypted = encrypt_token(tokens["refresh_token"])
        if existing:
            existing.refresh_token_encrypted = encrypted
            existing.status = EmailAccountStatus.active
        else:
            db.add(
                EmailAccount(
                    provider=provider_enum,
                    email_address=email_address,
                    refresh_token_encrypted=encrypted,
                    status=EmailAccountStatus.active,
                )
            )
        db.commit()
    except HTTPException as exc:
        return _callback_page("Connection failed", str(exc.detail))
    except RuntimeError as exc:
        # Most commonly TOKEN_ENCRYPTION_KEY missing/invalid on the server —
        # surfaced here instead of a bare 500 so it's actionable from the
        # popup itself rather than only in server logs.
        return _callback_page("Server not configured", str(exc))

    return _callback_page("Connected", f"Connected {email_address}.")


@router.post("/{account_id}/scan", response_model=list[CandidateEmailOut], dependencies=[Depends(get_current_user)])
def scan_account(account_id: uuid.UUID, payload: ScanRequest, db: Session = Depends(get_db)):
    account = _get_account(account_id, db)
    access_token = _ensure_access_token(account, db)
    service = _SERVICES[account.provider]
    return service.scan_inbox(access_token, payload.vendor_names)


@router.get(
    "/{account_id}/emails/{message_id}", response_model=EmailDetailOut, dependencies=[Depends(get_current_user)]
)
def get_email_detail(account_id: uuid.UUID, message_id: str, db: Session = Depends(get_db)):
    account = _get_account(account_id, db)
    access_token = _ensure_access_token(account, db)
    service = _SERVICES[account.provider]
    return service.fetch_email_detail(access_token, message_id)


@router.post(
    "/{account_id}/emails/{message_id}/move",
    response_model=MoveEmailResult,
    dependencies=[Depends(get_current_user)],
)
def move_email(account_id: uuid.UUID, message_id: str, db: Session = Depends(get_db)):
    account = _get_account(account_id, db)
    access_token = _ensure_access_token(account, db)
    service = _SERVICES[account.provider]
    folder_name = _ORDERS_LABEL_SETTING[account.provider](settings)
    mover = service.move_to_orders_label if account.provider == EmailProvider.gmail else service.move_to_orders_folder
    try:
        mover(access_token, message_id, folder_name)
        return MoveEmailResult(moved=True)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            return MoveEmailResult(
                moved=False,
                reason="permission",
                message=f'{account.provider.value.title()} didn\'t grant permission to move this email into '
                f'"{folder_name}". The order was still recorded — reconnect this account with full permissions '
                "if you'd like emails filed automatically.",
            )
        return MoveEmailResult(
            moved=False,
            reason="error",
            message=f'Could not move this email into "{folder_name}" (it\'s still in the inbox). '
            "The order was recorded successfully.",
        )
