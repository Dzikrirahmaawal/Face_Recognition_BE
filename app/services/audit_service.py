from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record(
    db: Session,
    *,
    action: str,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    description: str | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        description=description,
        ip_address=ip_address,
    )
    db.add(log)
    return log
