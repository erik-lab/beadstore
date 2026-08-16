import uuid
from datetime import datetime

from app.models.audit_log import AuditAction
from app.schemas.common import ORMModel, Page


class AuditLogRead(ORMModel):
    id: uuid.UUID
    table_name: str
    record_id: uuid.UUID
    action: AuditAction
    changes: str
    actor_id: uuid.UUID | None
    actor_email: str | None
    created_at: datetime


class AuditLogPage(Page):
    items: list[AuditLogRead]
