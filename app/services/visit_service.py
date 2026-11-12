from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import VisitStatus
from app.models.user import User
from app.models.visit import Visit
from app.repositories import employees as employees_repo
from app.repositories import visits as visits_repo
from app.repositories.base import paginate
from app.schemas.visit import VisitCreate, VisitUpdate
from app.services import audit_service, visitor_service


def get_or_404(db: Session, visit_id: uuid.UUID, for_update: bool = False) -> Visit:
    visit = visits_repo.get(db, visit_id, for_update=for_update)
    if visit is None:
        raise NotFoundError("Visit not found", error_code="VISIT_NOT_FOUND")
    return visit


def _validate_host(db: Session, host_employee_id: uuid.UUID | None) -> None:
    if host_employee_id is None:
        return
    employee = employees_repo.get(db, host_employee_id)
    if employee is None:
        raise NotFoundError("Host employee not found", error_code="HOST_EMPLOYEE_NOT_FOUND")
    if not employee.is_active:
        raise ConflictError("Host employee is inactive", error_code="HOST_EMPLOYEE_INACTIVE")


def create_visit(
    db: Session,
    *,
    data: VisitCreate,
    actor: User,
    ip_address: str | None,
) -> Visit:
    visitor = visitor_service.get_or_404(db, data.visitor_id, for_update=True)
    if not visitor.is_active:
        raise ConflictError("Visitor is inactive", error_code="VISITOR_INACTIVE")
    _validate_host(db, data.host_employee_id)
    active = visits_repo.get_active_for_visitor(db, visitor.id, for_update=True)
    if active is not None:
        raise ConflictError(
            "Visitor already has an active visit",
            error_code="ACTIVE_VISIT_EXISTS",
            details={"visit_id": str(active.id), "visit_status": active.visit_status.value},
        )
    visit = Visit(
        visitor_id=visitor.id,
        purpose=data.purpose,
        host_employee_id=data.host_employee_id,
        visit_status=VisitStatus.WAITING,
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
    audit_service.record(
        db,
        action="VISIT_CREATED",
        entity_type="visit",
        entity_id=visit.id,
        description=f"Visit created for visitor {visitor.visitor_code}",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(visit)
    return visit


def list_visits(
    db: Session,
    *,
    page: int,
    page_size: int,
    visitor_id: uuid.UUID | None,
    status: VisitStatus | None,
    date_from,
    date_to,
    search: str | None,
):
    stmt = visits_repo.list_visits(
        db,
        page,
        page_size,
        visitor_id=visitor_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return paginate(db, stmt, page, page_size)


def update_visit(
    db: Session,
    *,
    visit_id: uuid.UUID,
    data: VisitUpdate,
    actor: User,
    ip_address: str | None,
) -> Visit:
    visit = get_or_404(db, visit_id, for_update=True)
    if visit.visit_status in {VisitStatus.CHECKED_OUT, VisitStatus.CANCELLED}:
        raise ConflictError("Closed visits cannot be edited", error_code="VISIT_NOT_EDITABLE")
    changes = data.model_dump(exclude_unset=True)
    if "host_employee_id" in changes:
        _validate_host(db, changes["host_employee_id"])
    for field, value in changes.items():
        setattr(visit, field, value)
    audit_service.record(
        db,
        action="VISIT_UPDATED",
        entity_type="visit",
        entity_id=visit.id,
        description=f"Fields updated: {', '.join(sorted(changes.keys()))}",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(visit)
    return visit


def cancel_visit(
    db: Session,
    *,
    visit_id: uuid.UUID,
    reason: str | None,
    actor: User,
    ip_address: str | None,
) -> Visit:
    visit = get_or_404(db, visit_id, for_update=True)
    if visit.visit_status == VisitStatus.CANCELLED:
        raise ConflictError("Visit is already cancelled", error_code="VISIT_ALREADY_CANCELLED")
    if visit.visit_status == VisitStatus.CHECKED_OUT:
        raise ConflictError("Checked-out visits cannot be cancelled", error_code="VISIT_ALREADY_CLOSED")
    if visit.visit_status == VisitStatus.CHECKED_IN:
        raise ConflictError(
            "Visitor is checked in. Record check-out before cancelling.",
            error_code="VISIT_CHECKOUT_REQUIRED",
        )
    visit.visit_status = VisitStatus.CANCELLED
    visit.active_visit_key = None
    audit_service.record(
        db,
        action="VISIT_CANCELLED",
        entity_type="visit",
        entity_id=visit.id,
        description=(reason or "Visit cancelled")[:1000],
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(visit)
    return visit
