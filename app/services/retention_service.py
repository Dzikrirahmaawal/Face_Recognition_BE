from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, exists, false, select, true
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
from app.core.types import utcnow
from app.models.attendance import AttendanceLog
from app.models.enums import VisitStatus
from app.models.idempotency import IdempotencyRecord
from app.models.user import RefreshToken
from app.models.visit import Visit
from app.models.visitor import Visitor
from app.services import audit_service


@dataclass
class RetentionSummary:
    biometric_profiles_purged: int = 0
    inactive_visitors_scanned: int = 0
    idempotency_records_deleted: int = 0
    refresh_tokens_deleted: int = 0
    attendance_logs_deleted: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def purge_expired_data(
    db: Session,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> RetentionSummary:
    """Apply configured retention windows.

    This is intentionally a maintenance job, not a request-path operation.
    Run it from cron, a systemd timer, or a scheduled container job.
    """

    current = now or utcnow()
    visitor_cutoff = current - timedelta(days=settings.VISITOR_RETENTION_DAYS)
    attendance_cutoff = current - timedelta(days=settings.ATTENDANCE_RETENTION_DAYS)
    summary = RetentionSummary()

    active_visit_exists = exists().where(
        Visit.visitor_id == Visitor.id,
        Visit.visit_status.in_([VisitStatus.WAITING, VisitStatus.CHECKED_IN]),
    )
    expired_visitors = db.scalars(
        select(Visitor).where(
            Visitor.is_active == false(),
            Visitor.updated_at < visitor_cutoff,
            ~active_visit_exists,
        )
    ).all()
    summary.inactive_visitors_scanned = len(expired_visitors)
    for visitor in expired_visitors:
        for profile in visitor.face_profiles:
            if profile.embedding_data is None and not profile.is_active:
                continue
            profile.embedding_data = None
            profile.is_active = False
            profile.active_profile_key = None
            profile.deleted_at = current
            profile.deletion_reason = "RETENTION_EXPIRED"
            profile.updated_at = current
            summary.biometric_profiles_purged += 1
        audit_service.record(
            db,
            action="RETENTION_BIOMETRIC_PURGED",
            entity_type="visitor",
            entity_id=visitor.id,
            description="Biometric data purged after visitor retention window",
        )

    idempotency_result = db.execute(
        delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < current)
    )
    summary.idempotency_records_deleted = int(idempotency_result.rowcount or 0)

    refresh_result = db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < current)
    )
    summary.refresh_tokens_deleted = int(refresh_result.rowcount or 0)

    db.execute(
        delete(AttendanceLog).where(
            AttendanceLog.is_correction == true(),
            AttendanceLog.event_timestamp < attendance_cutoff,
        )
    )
    correction = aliased(AttendanceLog)
    not_referenced = ~exists().where(correction.correction_of_id == AttendanceLog.id)
    attendance_result = db.execute(
        delete(AttendanceLog).where(
            AttendanceLog.is_correction == false(),
            AttendanceLog.event_timestamp < attendance_cutoff,
            not_referenced,
        )
    )
    summary.attendance_logs_deleted = int(attendance_result.rowcount or 0)

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return summary
