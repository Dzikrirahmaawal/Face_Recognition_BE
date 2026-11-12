from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.consent import ConsentRecord
from app.models.enums import ConsentStatus, ConsentType


def latest_for_visitor(
    db: Session, visitor_id: uuid.UUID, consent_type: ConsentType
) -> ConsentRecord | None:
    stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.visitor_id == visitor_id, ConsentRecord.consent_type == consent_type)
        .order_by(ConsentRecord.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def is_biometric_authorized(db: Session, visitor_id: uuid.UUID) -> bool:
    record = latest_for_visitor(db, visitor_id, ConsentType.BIOMETRIC_PROCESSING)
    return bool(record and record.consent_status == ConsentStatus.GRANTED)


def list_for_visitor(db: Session, visitor_id: uuid.UUID) -> list[ConsentRecord]:
    stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.visitor_id == visitor_id)
        .order_by(ConsentRecord.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def add(db: Session, record: ConsentRecord) -> ConsentRecord:
    db.add(record)
    return record
