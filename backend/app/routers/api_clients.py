import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.api_keys import generate_api_key, hash_api_key
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.api_client import ApiClient
from app.models.enums import ApiClientStatus
from app.schemas.api_client import ApiClientCreate, ApiClientCreated, ApiClientRead

# Staff-only management of non-human API credentials (storefront app, Etsy
# integration) — see docs/design/api-tiers-work-plan.md. Distinct from
# core/security.py's get_api_client, which is what those credentials
# themselves authenticate *with*, elsewhere.
router = APIRouter(prefix="/api-clients", tags=["api-clients"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ApiClientRead])
def list_api_clients(db: Session = Depends(get_db)):
    return db.query(ApiClient).order_by(ApiClient.created_at.desc()).all()


@router.post("", response_model=ApiClientCreated, status_code=status.HTTP_201_CREATED)
def create_api_client(payload: ApiClientCreate, db: Session = Depends(get_db)):
    raw_key = generate_api_key()
    client = ApiClient(name=payload.name, kind=payload.kind, api_key_hash=hash_api_key(raw_key))
    db.add(client)
    db.commit()
    db.refresh(client)
    return ApiClientCreated(api_key=raw_key, **ApiClientRead.model_validate(client).model_dump())


@router.post("/{client_id}/revoke", response_model=ApiClientRead)
def revoke_api_client(client_id: uuid.UUID, db: Session = Depends(get_db)):
    client = db.get(ApiClient, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API client not found")
    client.status = ApiClientStatus.revoked
    db.commit()
    db.refresh(client)
    return client
