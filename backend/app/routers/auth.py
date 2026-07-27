import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.profile import Profile
from app.schemas.profile import ProfileRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=ProfileRead)
def read_me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, uuid.UUID(current_user.id))
    return profile
