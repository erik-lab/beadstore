import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.profile import Profile
from app.schemas.profile import THEME_VALUES, ProfileRead, ProfileUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=ProfileRead)
def read_me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, uuid.UUID(current_user.id))
    return profile


@router.patch("/me", response_model=ProfileRead)
def update_me(
    payload: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.theme is not None and payload.theme not in THEME_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"theme must be one of {THEME_VALUES}",
        )

    profile = db.get(Profile, uuid.UUID(current_user.id))
    update_fields = payload.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
