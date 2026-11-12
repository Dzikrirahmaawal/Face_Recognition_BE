from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import require_permissions
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.enums import VisitStatus
from app.models.user import User
from app.schemas.common import pagination_meta, success_payload
from app.schemas.visit import VisitCancelRequest, VisitCreate, VisitOut, VisitUpdate
from app.services import visit_service

router = APIRouter(prefix="/visits", tags=["Visits"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", status_code=201)
def create_visit(
    payload: VisitCreate,
    request: Request,
    user: User = Depends(require_permissions(Permission.VISIT_WRITE)),
    db: Session = Depends(get_db),
):
    visit = visit_service.create_visit(db, data=payload, actor=user, ip_address=_ip(request))
    return success_payload(
        data=VisitOut.model_validate(visit).model_dump(mode="json"),
        message="Visit created",
    )


@router.get("")
def list_visits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    visitor_id: uuid.UUID | None = Query(None),
    status: VisitStatus | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    search: str | None = Query(None, max_length=150),
    _: User = Depends(require_permissions(Permission.VISIT_READ)),
    db: Session = Depends(get_db),
):
    items, total = visit_service.list_visits(
        db,
        page=page,
        page_size=page_size,
        visitor_id=visitor_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return success_payload(
        data=[VisitOut.model_validate(item).model_dump(mode="json") for item in items],
        message="Visits retrieved",
        meta=pagination_meta(page, page_size, total),
    )


@router.get("/{visit_id}")
def get_visit(
    visit_id: uuid.UUID,
    _: User = Depends(require_permissions(Permission.VISIT_READ)),
    db: Session = Depends(get_db),
):
    visit = visit_service.get_or_404(db, visit_id)
    return success_payload(
        data=VisitOut.model_validate(visit).model_dump(mode="json"),
        message="Visit retrieved",
    )


@router.put("/{visit_id}")
def update_visit(
    visit_id: uuid.UUID,
    payload: VisitUpdate,
    request: Request,
    user: User = Depends(require_permissions(Permission.VISIT_WRITE)),
    db: Session = Depends(get_db),
):
    visit = visit_service.update_visit(
        db, visit_id=visit_id, data=payload, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=VisitOut.model_validate(visit).model_dump(mode="json"),
        message="Visit updated",
    )


@router.post("/{visit_id}/cancel")
def cancel_visit(
    visit_id: uuid.UUID,
    payload: VisitCancelRequest,
    request: Request,
    user: User = Depends(require_permissions(Permission.VISIT_WRITE)),
    db: Session = Depends(get_db),
):
    visit = visit_service.cancel_visit(
        db, visit_id=visit_id, reason=payload.reason, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=VisitOut.model_validate(visit).model_dump(mode="json"),
        message="Visit cancelled",
    )
