from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import require_permissions
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.user import User
from app.repositories import consent as consent_repo
from app.schemas.common import pagination_meta, success_payload
from app.schemas.visitor import (
    BiometricDeleteRequest,
    ConsentWithdrawRequest,
    VisitorCreate,
    VisitorOut,
    VisitorUpdate,
)
from app.services import visitor_service

router = APIRouter(prefix="/visitors", tags=["Visitors"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", status_code=201)
def create_visitor(
    payload: VisitorCreate,
    request: Request,
    user: User = Depends(require_permissions(Permission.VISITOR_WRITE)),
    db: Session = Depends(get_db),
):
    visitor = visitor_service.create_visitor(
        db, data=payload, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=VisitorOut.model_validate(visitor).model_dump(mode="json"),
        message="Visitor registered successfully",
    )


@router.get("")
def list_visitors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = Query(None, max_length=150),
    is_active: bool | None = Query(None),
    _: User = Depends(require_permissions(Permission.VISITOR_READ)),
    db: Session = Depends(get_db),
):
    items, total = visitor_service.list_visitors(
        db, page=page, page_size=page_size, search=search, is_active=is_active
    )
    return success_payload(
        data=[VisitorOut.model_validate(item).model_dump(mode="json") for item in items],
        message="Visitors retrieved",
        meta=pagination_meta(page, page_size, total),
    )


@router.get("/{visitor_id}")
def get_visitor(
    visitor_id: uuid.UUID,
    _: User = Depends(require_permissions(Permission.VISITOR_READ)),
    db: Session = Depends(get_db),
):
    visitor = visitor_service.get_or_404(db, visitor_id)
    return success_payload(
        data=VisitorOut.model_validate(visitor).model_dump(mode="json"),
        message="Visitor retrieved",
    )


@router.put("/{visitor_id}")
def update_visitor(
    visitor_id: uuid.UUID,
    payload: VisitorUpdate,
    request: Request,
    user: User = Depends(require_permissions(Permission.VISITOR_WRITE)),
    db: Session = Depends(get_db),
):
    visitor = visitor_service.update_visitor(
        db, visitor_id=visitor_id, data=payload, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=VisitorOut.model_validate(visitor).model_dump(mode="json"),
        message="Visitor updated",
    )


@router.delete("/{visitor_id}")
def deactivate_visitor(
    visitor_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permissions(Permission.VISITOR_DELETE)),
    db: Session = Depends(get_db),
):
    visitor = visitor_service.deactivate_visitor(
        db, visitor_id=visitor_id, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=VisitorOut.model_validate(visitor).model_dump(mode="json"),
        message="Visitor deactivated. Historical attendance remains available.",
    )


@router.post("/{visitor_id}/biometric/withdraw")
def withdraw_biometric_consent(
    visitor_id: uuid.UUID,
    payload: ConsentWithdrawRequest,
    request: Request,
    user: User = Depends(require_permissions(Permission.PRIVACY_MANAGE)),
    db: Session = Depends(get_db),
):
    visitor = visitor_service.withdraw_biometric_consent(
        db,
        visitor_id=visitor_id,
        reason=payload.reason,
        policy_version=payload.policy_version,
        actor=user,
        ip_address=_ip(request),
    )
    return success_payload(
        data=VisitorOut.model_validate(visitor).model_dump(mode="json"),
        message="Biometric consent withdrawn and face profiles deactivated",
    )


@router.delete("/{visitor_id}/biometric")
def delete_biometric_data(
    visitor_id: uuid.UUID,
    payload: BiometricDeleteRequest,
    request: Request,
    user: User = Depends(require_permissions(Permission.PRIVACY_MANAGE)),
    db: Session = Depends(get_db),
):
    visitor = visitor_service.delete_biometric_data(
        db,
        visitor_id=visitor_id,
        reason=payload.reason,
        actor=user,
        ip_address=_ip(request),
    )
    return success_payload(
        data=VisitorOut.model_validate(visitor).model_dump(mode="json"),
        message="Biometric data deleted. Attendance history is retained.",
    )


@router.get("/{visitor_id}/consents")
def list_consents(
    visitor_id: uuid.UUID,
    _: User = Depends(require_permissions(Permission.PRIVACY_MANAGE)),
    db: Session = Depends(get_db),
):
    visitor_service.get_or_404(db, visitor_id)
    records = consent_repo.list_for_visitor(db, visitor_id)
    return success_payload(
        data=[
            {
                "id": str(record.id),
                "consent_type": record.consent_type.value,
                "policy_version": record.policy_version,
                "consent_status": record.consent_status.value,
                "consented_at": record.consented_at,
                "withdrawn_at": record.withdrawn_at,
                "recorded_by": str(record.recorded_by) if record.recorded_by else None,
                "created_at": record.created_at,
            }
            for record in records
        ],
        message="Consent records retrieved",
    )
