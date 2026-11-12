from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.types import utcnow
from app.models.attendance import AttendanceLog
from app.models.enums import AttendanceEventType, AttendanceMethod, VisitStatus
from app.models.visit import Visit
from app.repositories import attendance as attendance_repo
from app.repositories import consent as consent_repo
from app.repositories import employees as employees_repo
from app.repositories import kiosks as kiosks_repo
from app.repositories import visits as visits_repo
from app.repositories.base import paginate
from app.schemas.attendance import CheckInRequest, CheckOutRequest
from app.services import audit_service, idempotency_service, visitor_service


def _visitor_summary(visitor) -> dict:  # noqa: ANN001
    return {
        "id": visitor.id,
        "visitor_code": visitor.visitor_code,
        "full_name": visitor.full_name,
        "company_name": visitor.company_name,
    }


def _response(
    *,
    message: str,
    visit: Visit,
    log: AttendanceLog,
) -> dict:
    return {
        "success": True,
        "message": message,
        "data": {
            "attendance_id": log.id,
            "visit_id": visit.id,
            "visitor": _visitor_summary(visit.visitor),
            "event_type": log.event_type.value,
            "event_timestamp": log.event_timestamp,
            "visit_status": visit.visit_status.value,
            "check_in_at": visit.check_in_at,
            "check_out_at": visit.check_out_at,
            "kiosk_id": log.kiosk_id,
        },
        "meta": None,
    }


def _validate_kiosk(db: Session, actor, requested_kiosk_id: uuid.UUID | None) -> uuid.UUID | None:
    if actor.kiosk is not None:
        if requested_kiosk_id is not None and requested_kiosk_id != actor.kiosk.id:
            raise AppError(
                "Kiosk token does not match the requested kiosk_id",
                status_code=403,
                error_code="KIOSK_MISMATCH",
            )
        return actor.kiosk.id
    if requested_kiosk_id is None:
        return None
    kiosk = kiosks_repo.get(db, requested_kiosk_id)
    if kiosk is None:
        raise NotFoundError("Kiosk not found", error_code="KIOSK_NOT_FOUND")
    if not kiosk.is_active:
        raise ConflictError("Kiosk is inactive", error_code="KIOSK_INACTIVE")
    return kiosk.id


def _validate_host(db: Session, host_employee_id: uuid.UUID | None) -> None:
    if host_employee_id is None:
        return
    employee = employees_repo.get(db, host_employee_id)
    if employee is None:
        raise NotFoundError("Host employee not found", error_code="HOST_EMPLOYEE_NOT_FOUND")
    if not employee.is_active:
        raise ConflictError("Host employee is inactive", error_code="HOST_EMPLOYEE_INACTIVE")


def _ensure_biometric_authorization(db: Session, visitor_id: uuid.UUID, method: AttendanceMethod) -> None:
    if method == AttendanceMethod.FACE and not consent_repo.is_biometric_authorized(db, visitor_id):
        raise AppError(
            "Biometric processing is not authorized for this visitor",
            status_code=403,
            error_code="BIOMETRIC_AUTHORIZATION_REQUIRED",
        )


def _idempotency_payload(data, effective_kiosk_id: uuid.UUID | None) -> dict:
    return {
        "visitor_id": data.visitor_id,
        "visit_id": data.visit_id,
        "purpose": getattr(data, "purpose", None),
        "host_employee_id": getattr(data, "host_employee_id", None),
        "method": data.method,
        "confidence_score": data.confidence_score,
        "kiosk_id": effective_kiosk_id,
    }


def check_in(
    db: Session,
    *,
    data: CheckInRequest,
    actor,
    ip_address: str | None,
    idempotency_key: str | None,
) -> tuple[int, dict]:
    effective_kiosk_id = _validate_kiosk(db, actor, data.kiosk_id)
    payload = _idempotency_payload(data, effective_kiosk_id)
    scope = "attendance:check-in"
    if idempotency_key:
        cached = idempotency_service.get_cached(db, idempotency_key, scope, payload)
        if cached is not None:
            return cached

    visitor = visitor_service.get_or_404(db, data.visitor_id, for_update=True)
    if not visitor.is_active:
        raise ConflictError("Visitor is inactive", error_code="VISITOR_INACTIVE")
    _ensure_biometric_authorization(db, visitor.id, data.method)
    _validate_host(db, data.host_employee_id)

    visit: Visit | None = None
    if data.visit_id is not None:
        visit = visits_repo.get(db, data.visit_id, for_update=True)
        if visit is None:
            raise NotFoundError("Visit not found", error_code="VISIT_NOT_FOUND")
        if visit.visitor_id != visitor.id:
            raise ConflictError("Visit does not belong to this visitor", error_code="VISIT_VISITOR_MISMATCH")
        if visit.visit_status in {VisitStatus.CHECKED_OUT, VisitStatus.CANCELLED}:
            raise ConflictError("Visit is already closed", error_code="VISIT_NOT_ACTIVE")
        if visit.visit_status == VisitStatus.CHECKED_IN:
            raise ConflictError(
                "Visitor is already checked in",
                error_code="ALREADY_CHECKED_IN",
                details={"visit_id": str(visit.id)},
            )
    else:
        visit = visits_repo.get_active_for_visitor(db, visitor.id, for_update=True)
        if visit is not None and visit.visit_status == VisitStatus.CHECKED_IN:
            raise ConflictError(
                "Visitor is already checked in",
                error_code="ALREADY_CHECKED_IN",
                details={"visit_id": str(visit.id)},
            )

    now = utcnow()
    if visit is None:
        visit = Visit(
            visitor_id=visitor.id,
            purpose=data.purpose,
            host_employee_id=data.host_employee_id,
            visit_status=VisitStatus.CHECKED_IN,
            check_in_at=now,
            active_visit_key=visitor.id,
        )
        visits_repo.add(db, visit)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(
                "Visitor already has an active visit",
                error_code="ACTIVE_VISIT_EXISTS",
            ) from exc
    else:
        visit.visit_status = VisitStatus.CHECKED_IN
        visit.check_in_at = now
        visit.active_visit_key = visitor.id
        if data.purpose and not visit.purpose:
            visit.purpose = data.purpose
        if data.host_employee_id and not visit.host_employee_id:
            visit.host_employee_id = data.host_employee_id

    existing = attendance_repo.get_original_for_visit(db, visit.id, AttendanceEventType.CHECK_IN)
    if existing is not None:
        raise ConflictError(
            "A CHECK_IN event already exists for this visit",
            error_code="DUPLICATE_ATTENDANCE",
        )

    log = AttendanceLog(
        visit_id=visit.id,
        visitor_id=visitor.id,
        event_type=AttendanceEventType.CHECK_IN,
        event_timestamp=now,
        kiosk_id=effective_kiosk_id,
        confidence_score=data.confidence_score,
        event_unique_key=f"{visit.id}:CHECK_IN",
        recorded_by_user_id=actor.user_id,
    )
    attendance_repo.add(db, log)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            cached = idempotency_service.get_cached(db, idempotency_key, scope, payload)
            if cached is not None:
                return cached
        raise ConflictError(
            "Check-in conflicted with a concurrent request",
            error_code="DUPLICATE_ATTENDANCE",
        ) from exc
    audit_service.record(
        db,
        action="ATTENDANCE_CHECK_IN",
        entity_type="visit",
        entity_id=visit.id,
        description=f"Visitor {visitor.visitor_code} checked in via {data.method.value}",
        user_id=actor.user_id,
        ip_address=ip_address,
    )
    response = _response(message="Visitor checked in successfully", visit=visit, log=log)
    if idempotency_key:
        idempotency_service.save(
            db,
            key=idempotency_key,
            scope=scope,
            payload=payload,
            status_code=201,
            body=response,
            user_id=actor.user_id,
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            cached = idempotency_service.get_cached(db, idempotency_key, scope, payload)
            if cached is not None:
                return cached
        raise ConflictError(
            "Check-in conflicted with a concurrent request",
            error_code="DUPLICATE_ATTENDANCE",
        ) from exc
    db.refresh(log)
    db.refresh(visit)
    response["data"]["attendance_id"] = log.id
    return 201, response


def check_out(
    db: Session,
    *,
    data: CheckOutRequest,
    actor,
    ip_address: str | None,
    idempotency_key: str | None,
) -> tuple[int, dict]:
    effective_kiosk_id = _validate_kiosk(db, actor, data.kiosk_id)
    payload = _idempotency_payload(data, effective_kiosk_id)
    scope = "attendance:check-out"
    if idempotency_key:
        cached = idempotency_service.get_cached(db, idempotency_key, scope, payload)
        if cached is not None:
            return cached

    visitor = visitor_service.get_or_404(db, data.visitor_id, for_update=True)
    if not visitor.is_active:
        raise ConflictError("Visitor is inactive", error_code="VISITOR_INACTIVE")
    _ensure_biometric_authorization(db, visitor.id, data.method)

    visit: Visit | None = None
    if data.visit_id is not None:
        visit = visits_repo.get(db, data.visit_id, for_update=True)
        if visit is None:
            raise NotFoundError("Visit not found", error_code="VISIT_NOT_FOUND")
        if visit.visitor_id != visitor.id:
            raise ConflictError("Visit does not belong to this visitor", error_code="VISIT_VISITOR_MISMATCH")
        if visit.visit_status == VisitStatus.CHECKED_OUT:
            raise ConflictError("Visitor is already checked out", error_code="ALREADY_CHECKED_OUT")
        if visit.visit_status != VisitStatus.CHECKED_IN:
            raise ConflictError("Visitor is not checked in", error_code="NOT_CHECKED_IN")
    else:
        visit = visits_repo.get_active_for_visitor(db, visitor.id, for_update=True)
        if visit is None:
            raise ConflictError("Visitor has no active visit", error_code="NO_ACTIVE_VISIT")
        if visit.visit_status != VisitStatus.CHECKED_IN:
            raise ConflictError("Visitor is not checked in", error_code="NOT_CHECKED_IN")

    now = utcnow()
    existing = attendance_repo.get_original_for_visit(db, visit.id, AttendanceEventType.CHECK_OUT)
    if existing is not None:
        raise ConflictError(
            "A CHECK_OUT event already exists for this visit",
            error_code="DUPLICATE_ATTENDANCE",
        )

    visit.visit_status = VisitStatus.CHECKED_OUT
    visit.check_out_at = now
    visit.active_visit_key = None
    log = AttendanceLog(
        visit_id=visit.id,
        visitor_id=visitor.id,
        event_type=AttendanceEventType.CHECK_OUT,
        event_timestamp=now,
        kiosk_id=effective_kiosk_id,
        confidence_score=data.confidence_score,
        event_unique_key=f"{visit.id}:CHECK_OUT",
        recorded_by_user_id=actor.user_id,
    )
    attendance_repo.add(db, log)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            cached = idempotency_service.get_cached(db, idempotency_key, scope, payload)
            if cached is not None:
                return cached
        raise ConflictError(
            "Check-out conflicted with a concurrent request",
            error_code="DUPLICATE_ATTENDANCE",
        ) from exc
    audit_service.record(
        db,
        action="ATTENDANCE_CHECK_OUT",
        entity_type="visit",
        entity_id=visit.id,
        description=f"Visitor {visitor.visitor_code} checked out via {data.method.value}",
        user_id=actor.user_id,
        ip_address=ip_address,
    )
    response = _response(message="Visitor checked out successfully", visit=visit, log=log)
    if idempotency_key:
        idempotency_service.save(
            db,
            key=idempotency_key,
            scope=scope,
            payload=payload,
            status_code=200,
            body=response,
            user_id=actor.user_id,
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            cached = idempotency_service.get_cached(db, idempotency_key, scope, payload)
            if cached is not None:
                return cached
        raise ConflictError(
            "Check-out conflicted with a concurrent request",
            error_code="DUPLICATE_ATTENDANCE",
        ) from exc
    db.refresh(log)
    db.refresh(visit)
    response["data"]["attendance_id"] = log.id
    return 200, response


def list_attendance(
    db: Session,
    *,
    page: int,
    page_size: int,
    visitor_id: uuid.UUID | None,
    event_type: AttendanceEventType | None,
    date_from: datetime | None,
    date_to: datetime | None,
    kiosk_id: uuid.UUID | None,
):
    stmt = attendance_repo.list_attendance(
        db,
        page,
        page_size,
        visitor_id=visitor_id,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
        kiosk_id=kiosk_id,
    )
    return paginate(db, stmt, page, page_size)


def get_attendance_or_404(db: Session, attendance_id: uuid.UUID) -> AttendanceLog:
    log = attendance_repo.get(db, attendance_id)
    if log is None:
        raise NotFoundError("Attendance record not found", error_code="ATTENDANCE_NOT_FOUND")
    return log


def correct_attendance(
    db: Session,
    *,
    attendance_id: uuid.UUID,
    corrected_event_type: AttendanceEventType,
    corrected_timestamp: datetime,
    reason: str,
    actor,
    ip_address: str | None,
) -> AttendanceLog:
    original = get_attendance_or_404(db, attendance_id)
    if original.is_correction:
        raise ConflictError("Corrections cannot be corrected", error_code="INVALID_CORRECTION_TARGET")
    if corrected_event_type != original.event_type:
        raise AppError(
            "Changing an event type is not supported. Cancel the visit and create a new one instead.",
            status_code=422,
            error_code="UNSUPPORTED_CORRECTION",
        )
    correction = AttendanceLog(
        visit_id=original.visit_id,
        visitor_id=original.visitor_id,
        event_type=corrected_event_type,
        event_timestamp=corrected_timestamp,
        kiosk_id=original.kiosk_id,
        confidence_score=original.confidence_score,
        is_correction=True,
        correction_of_id=original.id,
        correction_reason=reason[:255],
        recorded_by_user_id=actor.user_id,
    )
    attendance_repo.add(db, correction)
    visit = visits_repo.get(db, original.visit_id, for_update=True)
    if visit is not None:
        if corrected_event_type == AttendanceEventType.CHECK_IN:
            visit.check_in_at = corrected_timestamp
        else:
            visit.check_out_at = corrected_timestamp
    audit_service.record(
        db,
        action="ATTENDANCE_CORRECTED",
        entity_type="attendance_log",
        entity_id=original.id,
        description=f"Correction appended. Reason: {reason}"[:1000],
        user_id=actor.user_id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(correction)
    return correction
