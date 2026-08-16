import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.schemas.sale import SaleCreate, SaleDetailRead, SaleRead
from app.services import sales_service

router = APIRouter(prefix="/sales", tags=["sales"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[SaleRead])
def list_sales(db: Session = Depends(get_db), limit: int = Query(default=50, le=200), offset: int = 0):
    return sales_service.list_sales(db, limit=limit, offset=offset)


@router.post("", response_model=SaleDetailRead, status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)):
    return sales_service.create_sale(db, payload)


@router.get("/{sale_id}", response_model=SaleDetailRead)
def get_sale(sale_id: uuid.UUID, db: Session = Depends(get_db)):
    return sales_service.get_sale_or_404(db, sale_id)
