from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_kiosk_token, hash_kiosk_token
from app.models.kiosk import Kiosk
from app.models.user import User
from app.repositories import kiosks as kiosks_repo
from app.repositories.base import paginate
from app.schemas.kiosk import KioskCreate
from app.services import audit_service


def get_or_404(db: Session, kiosk_id: uuid.UUID) -> Kiosk:
    kiosk = kiosks_repo.get(db, kiosk_id)
    if kiosk is None:
        raise NotFoundError("Kiosk not found", error_code="KIOSK_NOT_FOUND")
    return kiosk


def create_kiosk(
    db: Session, *, data: KioskCreate, actor: User, ip_address: str | None
) -> tuple[Kiosk, str]:
    if kiosks_repo.get_by_code(db, data.kiosk_code):
        raise ConflictError("Kiosk code is already in use", error_code="KIOSK_CODE_EXISTS")
    token = generate_kiosk_token()
    kiosk = Kiosk(
        kiosk_code=data.kiosk_code,
        device_name=data.device_name,
        device_token_hash=hash_kiosk_token(token),
        location=data.location,
        is_active=True,
    )
    kiosks_repo.add(db, kiosk)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Kiosk violates a unique constraint", error_code="KIOSK_CONFLICT") from exc
    audit_service.record(
        db,
        action="KIOSK_CREATED",
        entity_type="kiosk",
        entity_id=kiosk.id,
        description=f"Kiosk {kiosk.kiosk_code} created",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(kiosk)
    return kiosk, token


def list_kiosks(db: Session, *, page: int, page_size: int, is_active: bool | None):
    stmt = kiosks_repo.list_kiosks(db, page, page_size, is_active=is_active)
    return paginate(db, stmt, page, page_size)


def set_kiosk_status(
    db: Session, *, kiosk_id: uuid.UUID, is_active: bool, actor: User, ip_address: str | None
) -> Kiosk:
    kiosk = kiosks_repo.get(db, kiosk_id, for_update=True)
    if kiosk is None:
        raise NotFoundError("Kiosk not found", error_code="KIOSK_NOT_FOUND")
    kiosk.is_active = is_active
    audit_service.record(
        db,
        action="KIOSK_STATUS_CHANGED",
        entity_type="kiosk",
        entity_id=kiosk.id,
        description=f"Kiosk active={is_active}",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(kiosk)
    return kiosk
