from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import Actor, require_actor, require_permissions
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.user import User
from app.repositories import audit as audit_repo
from app.repositories.base import paginate
from app.schemas.admin import AuditLogOut, UserCreate, UserUpdate
from app.schemas.attendance import AttendanceCorrectionRequest, AttendanceLogOut
from app.schemas.auth import UserOut
from app.schemas.common import pagination_meta, success_payload
from app.services import attendance_service, auth_service, user_service

router = APIRouter(prefix="/admin", tags=["Administration"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    role: str | None = Query(None, max_length=30),
    is_active: bool | None = Query(None),
    _: User = Depends(require_permissions(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    items, total = user_service.list_users(
        db, page=page, page_size=page_size, role=role, is_active=is_active
    )
    return success_payload(
        data=[UserOut.model_validate(item).model_dump(mode="json") for item in items],
        message="Users retrieved",
        meta=pagination_meta(page, page_size, total),
    )


@router.post("/users", status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    actor: User = Depends(require_permissions(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    user = auth_service.create_user(
        db,
        username=payload.username,
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        role=payload.role,
        actor=actor,
        ip_address=_ip(request),
    )
    return success_payload(
        data=UserOut.model_validate(user).model_dump(mode="json"),
        message="User created",
    )


@router.patch("/users/{user_id}")
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    actor: User = Depends(require_permissions(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    user = user_service.update_user(
        db, user_id=user_id, data=payload, actor=actor, ip_address=_ip(request)
    )
    return success_payload(
        data=UserOut.model_validate(user).model_dump(mode="json"),
        message="User updated",
    )


@router.get("/audit-logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None, max_length=100),
    entity_type: str | None = Query(None, max_length=100),
    _: User = Depends(require_permissions(Permission.AUDIT_READ)),
    db: Session = Depends(get_db),
):
    stmt = audit_repo.list_logs(
        db, page, page_size, user_id=user_id, action=action, entity_type=entity_type
    )
    items, total = paginate(db, stmt, page, page_size)
    return success_payload(
        data=[AuditLogOut.model_validate(item).model_dump(mode="json") for item in items],
        message="Audit logs retrieved",
        meta=pagination_meta(page, page_size, total),
    )


@router.post("/attendance/{attendance_id}/correct")
def correct_attendance(
    attendance_id: uuid.UUID,
    payload: AttendanceCorrectionRequest,
    request: Request,
    actor: Actor = Depends(require_actor(Permission.ATTENDANCE_CORRECT, allow_kiosk=False)),
    db: Session = Depends(get_db),
):
    log = attendance_service.correct_attendance(
        db,
        attendance_id=attendance_id,
        corrected_event_type=payload.corrected_event_type,
        corrected_timestamp=payload.corrected_timestamp,
        reason=payload.reason,
        actor=actor,
        ip_address=_ip(request),
    )
    return success_payload(
        data=AttendanceLogOut.model_validate(log).model_dump(mode="json"),
        message="Correction appended to the attendance history",
    )
