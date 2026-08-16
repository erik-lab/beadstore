import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogPage, AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    db: Session = Depends(get_db),
    table_name: str | None = None,
    record_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    query = db.query(AuditLog)
    if table_name:
        query = query.filter(AuditLog.table_name == table_name)
    if record_id:
        query = query.filter(AuditLog.record_id == record_id)
    total = query.count()
    items = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/tables", response_model=list[str])
def list_audited_tables(db: Session = Depends(get_db)):
    rows = db.query(AuditLog.table_name).distinct().order_by(AuditLog.table_name).all()
    return [value for (value,) in rows]
