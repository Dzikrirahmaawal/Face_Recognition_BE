from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import Actor, require_actor, require_permissions
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.enums import AttendanceEventType
from app.models.user import User
from app.schemas.attendance import AttendanceLogOut, CheckInRequest, CheckOutRequest
from app.schemas.common import pagination_meta, success_payload
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/check-in")
def check_in(
    payload: CheckInRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    actor: Actor = Depends(require_actor(Permission.ATTENDANCE_WRITE)),
    db: Session = Depends(get_db),
):
    status_code, body = attendance_service.check_in(
        db,
        data=payload,
        actor=actor,
        ip_address=actor.ip_address,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


@router.post("/check-out")
def check_out(
    payload: CheckOutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    actor: Actor = Depends(require_actor(Permission.ATTENDANCE_WRITE)),
    db: Session = Depends(get_db),
):
    status_code, body = attendance_service.check_out(
        db,
        data=payload,
        actor=actor,
        ip_address=actor.ip_address,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


@router.get("")
def list_attendance(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    visitor_id: uuid.UUID | None = Query(None),
    event_type: AttendanceEventType | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    kiosk_id: uuid.UUID | None = Query(None),
    _: User = Depends(require_permissions(Permission.ATTENDANCE_READ)),
    db: Session = Depends(get_db),
):
    items, total = attendance_service.list_attendance(
        db,
        page=page,
        page_size=page_size,
        visitor_id=visitor_id,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
        kiosk_id=kiosk_id,
    )
    return success_payload(
        data=[AttendanceLogOut.model_validate(item).model_dump(mode="json") for item in items],
        message="Attendance records retrieved",
        meta=pagination_meta(page, page_size, total),
    )


@router.get("/{attendance_id}")
def get_attendance(
    attendance_id: uuid.UUID,
    _: User = Depends(require_permissions(Permission.ATTENDANCE_READ)),
    db: Session = Depends(get_db),
):
    log = attendance_service.get_attendance_or_404(db, attendance_id)
    return success_payload(
        data=AttendanceLogOut.model_validate(log).model_dump(mode="json"),
        message="Attendance record retrieved",
    )
