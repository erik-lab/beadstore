import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.hint import Hint
from app.schemas.hint import HintCreate, HintRead, HintUpdate

router = APIRouter(prefix="/hints", tags=["hints"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[HintRead])
def list_hints(db: Session = Depends(get_db), page: str | None = None):
    query = db.query(Hint)
    if page:
        query = query.filter(Hint.page == page)
    return query.order_by(Hint.page, Hint.item_key).all()


@router.post("", response_model=HintRead, status_code=status.HTTP_201_CREATED)
def create_hint(payload: HintCreate, db: Session = Depends(get_db)):
    hint = Hint(**payload.model_dump())
    db.add(hint)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A hint for page '{payload.page}' / item '{payload.item_key}' already exists",
        )
    db.refresh(hint)
    return hint


@router.patch("/{hint_id}", response_model=HintRead)
def update_hint(hint_id: uuid.UUID, payload: HintUpdate, db: Session = Depends(get_db)):
    hint = db.get(Hint, hint_id)
    if hint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hint not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hint, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A hint for that page/item already exists",
        )
    db.refresh(hint)
    return hint


@router.delete("/{hint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hint(hint_id: uuid.UUID, db: Session = Depends(get_db)):
    hint = db.get(Hint, hint_id)
    if hint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hint not found")
    db.delete(hint)
    db.commit()
