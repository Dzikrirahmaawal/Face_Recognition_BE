from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def add(db: Session, log: AuditLog) -> AuditLog:
    db.add(log)
    return log


def list_logs(
    db: Session,
    page: int,
    page_size: int,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    return stmt
