import datetime
import decimal
import enum
import json
import uuid

from sqlalchemy import DateTime, Enum, Index, String, Uuid, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base
from app.models.mixins import UUIDPKMixin, utcnow


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"


class AuditLog(UUIDPKMixin, Base):
    """An immutable record of a create/update/delete on an audited table.

    Populated automatically by the `before_flush` listener below for every
    model that mixes in AuditMixin — nothing in the routers needs to call
    into this. `changes` is a JSON-encoded dict: {field: {"old": ..., "new":
    ...}} for updates, {field: value} (the full row) for creates/deletes.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_table_record", "table_name", "record_id"),)

    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction, native_enum=False, length=20), nullable=False)
    changes: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def _json_default(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, enum.Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _snapshot(obj) -> dict:
    # Note: for a not-yet-inserted object, columns with a Python-side
    # `default=` (e.g. status enums, created_at) haven't been resolved yet
    # at this point in the flush and will show as null here even though the
    # actual inserted row gets the default — a cosmetic gap in the "create"
    # snapshot only, not in the record itself.
    from sqlalchemy import inspect as sa_inspect

    state = sa_inspect(obj)
    return {attr.key: getattr(obj, attr.key) for attr in state.mapper.column_attrs}


def _diff(obj) -> dict | None:
    from sqlalchemy import inspect as sa_inspect

    state = sa_inspect(obj)
    changes = {}
    for attr in state.mapper.column_attrs:
        history = state.get_history(attr.key, True)
        if not history.has_changes():
            continue
        old_value = history.deleted[0] if history.deleted else None
        new_value = history.added[0] if history.added else getattr(obj, attr.key)
        changes[attr.key] = {"old": old_value, "new": new_value}
    return changes or None


@event.listens_for(Session, "before_flush")
def _capture_audit_trail(session: Session, flush_context, instances) -> None:
    from app.models.mixins import AuditMixin

    actor_id = session.info.get("actor_id")
    actor_email = session.info.get("actor_email")

    new_objs = [o for o in session.new if isinstance(o, AuditMixin)]
    dirty_objs = [o for o in session.dirty if isinstance(o, AuditMixin) and session.is_modified(o)]
    deleted_objs = [o for o in session.deleted if isinstance(o, AuditMixin)]

    for obj in new_objs:
        # The id column's default (uuid.uuid4) is normally applied during
        # the insert itself, which happens after this listener runs — assign
        # it early so the audit row can reference the record it describes.
        if obj.id is None:
            obj.id = uuid.uuid4()
        obj.created_by = obj.created_by or actor_id
        obj.updated_by = obj.updated_by or actor_id

    for obj in dirty_objs:
        obj.updated_by = actor_id

    entries = []
    for obj in new_objs:
        entries.append((obj, AuditAction.create, _snapshot(obj)))
    for obj in dirty_objs:
        changes = _diff(obj)
        if changes is None:
            continue
        entries.append((obj, AuditAction.update, changes))
    for obj in deleted_objs:
        entries.append((obj, AuditAction.delete, _snapshot(obj)))

    for obj, action, changes in entries:
        session.add(
            AuditLog(
                table_name=obj.__tablename__,
                record_id=obj.id,
                action=action,
                changes=json.dumps(changes, default=_json_default),
                actor_id=actor_id,
                actor_email=actor_email,
            )
        )
