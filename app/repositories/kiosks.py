from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kiosk import Kiosk


def get(db: Session, kiosk_id: uuid.UUID, for_update: bool = False) -> Kiosk | None:
    stmt = select(Kiosk).where(Kiosk.id == kiosk_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def get_by_code(db: Session, code: str) -> Kiosk | None:
    return db.scalars(select(Kiosk).where(Kiosk.kiosk_code == code)).first()


def get_by_token_hash(db: Session, token_hash: str) -> Kiosk | None:
    return db.scalars(select(Kiosk).where(Kiosk.device_token_hash == token_hash)).first()


def list_kiosks(db: Session, page: int, page_size: int, is_active: bool | None = None):
    stmt = select(Kiosk).order_by(Kiosk.created_at.desc())
    if is_active is not None:
        stmt = stmt.where(Kiosk.is_active.is_(is_active))
    return stmt


def add(db: Session, kiosk: Kiosk) -> Kiosk:
    db.add(kiosk)
    return kiosk
