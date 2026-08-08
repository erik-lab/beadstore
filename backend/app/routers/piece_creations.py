import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.enums import PieceCreationStatus
from app.models.piece_creation import PieceCreation
from app.schemas.piece_creation import PieceCreationCreate, PieceCreationRead
from app.services import piece_service

router = APIRouter(prefix="/piece-creations", tags=["piece-creations"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PieceCreationRead])
def list_piece_creations(
    db: Session = Depends(get_db),
    product_id: uuid.UUID | None = None,
    status_filter: PieceCreationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    query = db.query(PieceCreation)
    if product_id:
        query = query.filter(PieceCreation.product_id == product_id)
    if status_filter:
        query = query.filter(PieceCreation.status == status_filter)
    return query.order_by(PieceCreation.created_date.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=PieceCreationRead, status_code=status.HTTP_201_CREATED)
def create_piece_creation(payload: PieceCreationCreate, db: Session = Depends(get_db)):
    return piece_service.create_piece(db, payload)


@router.get("/{piece_creation_id}", response_model=PieceCreationRead)
def get_piece_creation(piece_creation_id: uuid.UUID, db: Session = Depends(get_db)):
    piece_creation = db.get(PieceCreation, piece_creation_id)
    if piece_creation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Piece creation not found")
    return piece_creation


@router.post("/{piece_creation_id}/cancel", response_model=PieceCreationRead)
def cancel_piece_creation(piece_creation_id: uuid.UUID, db: Session = Depends(get_db)):
    piece_creation = db.get(PieceCreation, piece_creation_id)
    if piece_creation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Piece creation not found")
    return piece_service.cancel_piece_creation(db, piece_creation)
