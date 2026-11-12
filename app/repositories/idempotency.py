from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyRecord


def get(db: Session, key: str) -> IdempotencyRecord | None:
    return db.scalars(select(IdempotencyRecord).where(IdempotencyRecord.key == key)).first()


def add(db: Session, record: IdempotencyRecord) -> IdempotencyRecord:
    db.add(record)
    return record


def delete_expired(db: Session, now: datetime) -> int:
    result = db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < now))
    return result.rowcount or 0
