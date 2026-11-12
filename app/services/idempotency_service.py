from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError
from app.core.types import ensure_utc, utcnow
from app.models.idempotency import IdempotencyRecord
from app.repositories import idempotency as idempotency_repo


def request_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_cached(db: Session, key: str, scope: str, payload: Any) -> tuple[int, dict[str, Any]] | None:
    record = idempotency_repo.get(db, key)
    if record is None:
        return None
    if record.scope != scope:
        raise ConflictError(
            "Idempotency key was already used for a different operation",
            error_code="IDEMPOTENCY_KEY_CONFLICT",
        )
    expires_at = ensure_utc(record.expires_at)
    if expires_at is not None and expires_at < utcnow():
        db.delete(record)
        db.flush()
        return None
    if record.request_hash != request_hash(payload):
        raise ConflictError(
            "Idempotency key was already used with a different request payload",
            error_code="IDEMPOTENCY_KEY_REUSED",
        )
    return record.response_status, json.loads(record.response_body)


def save(
    db: Session,
    *,
    key: str,
    scope: str,
    payload: Any,
    status_code: int,
    body: dict[str, Any],
    user_id: uuid.UUID | None = None,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        key=key[:128],
        scope=scope,
        request_hash=request_hash(payload),
        response_status=status_code,
        response_body=json.dumps(body, default=str),
        user_id=user_id,
        expires_at=utcnow() + timedelta(hours=settings.IDEMPOTENCY_TTL_HOURS),
    )
    return idempotency_repo.add(db, record)
