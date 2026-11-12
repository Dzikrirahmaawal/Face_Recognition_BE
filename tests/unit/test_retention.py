from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.types import utcnow
from app.models import (
    AttendanceEventType,
    AttendanceLog,
    FaceProfile,
    IdempotencyRecord,
    RefreshToken,
    Visit,
    VisitStatus,
    Visitor,
)
from app.services.retention_service import purge_expired_data


def _expired_records(db: Session, user_id: uuid.UUID) -> tuple[Visitor, FaceProfile, AttendanceLog, IdempotencyRecord]:
    now = utcnow()
    old = now - timedelta(days=max(settings.VISITOR_RETENTION_DAYS, settings.ATTENDANCE_RETENTION_DAYS) + 5)
    visitor = Visitor(
        visitor_code=f"VIS-{uuid.uuid4().hex[:10]}",
        full_name="Expired Visitor",
        is_active=False,
        created_at=old,
        updated_at=old,
    )
    db.add(visitor)
    db.flush()
    profile = FaceProfile(
        visitor_id=visitor.id,
        embedding_data=b"encrypted-embedding",
        model_version="test",
        embedding_version="1",
        is_active=True,
        active_profile_key=visitor.id,
        enrolled_at=old,
        updated_at=old,
    )
    visit = Visit(
        visitor_id=visitor.id,
        visit_status=VisitStatus.CHECKED_OUT,
        check_in_at=old,
        check_out_at=old,
        active_visit_key=None,
    )
    db.add_all([profile, visit])
    db.flush()
    log = AttendanceLog(
        visit_id=visit.id,
        visitor_id=visitor.id,
        event_type=AttendanceEventType.CHECK_IN,
        event_timestamp=old,
        event_unique_key=f"{visit.id}:CHECK_IN",
    )
    idem = IdempotencyRecord(
        key=f"expired-{uuid.uuid4().hex}",
        scope="attendance:check-in",
        request_hash="0" * 64,
        response_status=201,
        response_body="{}",
        expires_at=now - timedelta(hours=1),
    )
    token = RefreshToken(
        user_id=user_id,
        token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        jti=uuid.uuid4(),
        expires_at=now - timedelta(days=1),
        created_at=old,
    )
    db.add_all([log, idem, token])
    db.commit()
    return visitor, profile, log, idem


def test_purge_expired_data(db: Session, admin_user):
    visitor, profile, log, idem = _expired_records(db, admin_user.id)
    summary = purge_expired_data(db, now=utcnow())
    assert summary.inactive_visitors_scanned == 1
    assert summary.biometric_profiles_purged == 1
    assert summary.idempotency_records_deleted == 1
    assert summary.refresh_tokens_deleted == 1
    assert summary.attendance_logs_deleted == 1

    db.refresh(profile)
    assert profile.embedding_data is None
    assert profile.is_active is False
    assert profile.deletion_reason == "RETENTION_EXPIRED"
    assert db.get(AttendanceLog, log.id) is None
    assert db.get(IdempotencyRecord, idem.id) is None
    assert db.get(Visitor, visitor.id) is not None


def test_purge_dry_run_does_not_commit(db: Session, admin_user):
    visitor, profile, log, idem = _expired_records(db, admin_user.id)
    summary = purge_expired_data(db, now=utcnow(), dry_run=True)
    assert summary.biometric_profiles_purged == 1
    assert summary.attendance_logs_deleted == 1

    db.expire_all()
    assert db.get(AttendanceLog, log.id) is not None
    assert db.get(IdempotencyRecord, idem.id) is not None
    assert db.get(FaceProfile, profile.id).embedding_data == b"encrypted-embedding"
