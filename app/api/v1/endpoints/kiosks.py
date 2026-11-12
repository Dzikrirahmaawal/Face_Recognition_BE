from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import require_permissions
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.common import pagination_meta, success_payload
from app.schemas.kiosk import KioskCreate, KioskOut, KioskStatusUpdate
from app.services import kiosk_service

router = APIRouter(prefix="/kiosks", tags=["Kiosks"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", status_code=201)
def create_kiosk(
    payload: KioskCreate,
    request: Request,
    user: User = Depends(require_permissions(Permission.KIOSK_MANAGE)),
    db: Session = Depends(get_db),
):
    kiosk, token = kiosk_service.create_kiosk(db, data=payload, actor=user, ip_address=_ip(request))
    data = KioskOut.model_validate(kiosk).model_dump(mode="json")
    data["device_token"] = token
    return success_payload(
        data=data,
        message="Kiosk created. Store the device token securely; it will not be shown again.",
    )


@router.get("")
def list_kiosks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    is_active: bool | None = Query(None),
    _: User = Depends(require_permissions(Permission.KIOSK_READ)),
    db: Session = Depends(get_db),
):
    items, total = kiosk_service.list_kiosks(db, page=page, page_size=page_size, is_active=is_active)
    return success_payload(
        data=[KioskOut.model_validate(item).model_dump(mode="json") for item in items],
        message="Kiosks retrieved",
        meta=pagination_meta(page, page_size, total),
    )


@router.get("/{kiosk_id}")
def get_kiosk(
    kiosk_id: uuid.UUID,
    _: User = Depends(require_permissions(Permission.KIOSK_READ)),
    db: Session = Depends(get_db),
):
    kiosk = kiosk_service.get_or_404(db, kiosk_id)
    return success_payload(
        data=KioskOut.model_validate(kiosk).model_dump(mode="json"),
        message="Kiosk retrieved",
    )


@router.patch("/{kiosk_id}/status")
def set_kiosk_status(
    kiosk_id: uuid.UUID,
    payload: KioskStatusUpdate,
    request: Request,
    user: User = Depends(require_permissions(Permission.KIOSK_MANAGE)),
    db: Session = Depends(get_db),
):
    kiosk = kiosk_service.set_kiosk_status(
        db, kiosk_id=kiosk_id, is_active=payload.is_active, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=KioskOut.model_validate(kiosk).model_dump(mode="json"),
        message="Kiosk status updated",
    )
