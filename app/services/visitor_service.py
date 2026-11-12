from __future__ import annotations

import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.types import utcnow
from app.models.consent import ConsentRecord
from app.models.enums import ConsentStatus, ConsentType
from app.models.user import User
from app.models.visitor import FaceProfile, Visitor
from app.repositories import consent as consent_repo
from app.repositories import visitors as visitors_repo
from app.schemas.visitor import VisitorCreate, VisitorUpdate
from app.services import audit_service


def _generate_visitor_code(db: Session) -> str:
    for _ in range(10):
        code = f"VIS-{utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"
        if visitors_repo.get_by_code(db, code) is None:
            return code
    raise ConflictError("Could not allocate a unique visitor code", error_code="VISITOR_CODE_EXHAUSTED")


def get_or_404(db: Session, visitor_id: uuid.UUID, for_update: bool = False) -> Visitor:
    visitor = visitors_repo.get(db, visitor_id, for_update=for_update)
    if visitor is None:
        raise NotFoundError("Visitor not found", error_code="VISITOR_NOT_FOUND")
    return visitor


def create_visitor(
    db: Session,
    *,
    data: VisitorCreate,
    actor: User | None,
    ip_address: str | None,
    commit: bool = True,
) -> Visitor:
    visitor = Visitor(
        visitor_code=_generate_visitor_code(db),
        full_name=data.full_name.strip(),
        identity_number=data.identity_number,
        company_name=data.company_name,
        phone_number=data.phone_number,
        email=str(data.email).lower() if data.email else None,
        is_active=True,
    )
    visitors_repo.add(db, visitor)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A visitor with this identity number already exists", error_code="VISITOR_EXISTS") from exc
    audit_service.record(
        db,
        action="VISITOR_CREATED",
        entity_type="visitor",
        entity_id=visitor.id,
        description=f"Visitor {visitor.visitor_code} created",
        user_id=actor.id if actor else None,
        ip_address=ip_address,
    )
    if commit:
        db.commit()
        db.refresh(visitor)
    return visitor


def list_visitors(
    db: Session,
    *,
    page: int,
    page_size: int,
    search: str | None,
    is_active: bool | None,
):
    from app.repositories.base import paginate

    stmt = visitors_repo.list_visitors(db, page, page_size, search=search, is_active=is_active)
    items, total = paginate(db, stmt, page, page_size)
    return items, total


def update_visitor(
    db: Session,
    *,
    visitor_id: uuid.UUID,
    data: VisitorUpdate,
    actor: User,
    ip_address: str | None,
) -> Visitor:
    visitor = get_or_404(db, visitor_id)
    changes = data.model_dump(exclude_unset=True)
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).lower()
    for field, value in changes.items():
        setattr(visitor, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Visitor update violates a unique constraint", error_code="VISITOR_CONFLICT") from exc
    audit_service.record(
        db,
        action="VISITOR_UPDATED",
        entity_type="visitor",
        entity_id=visitor.id,
        description=f"Fields updated: {', '.join(sorted(changes.keys()))}",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(visitor)
    return visitor


def deactivate_visitor(
    db: Session,
    *,
    visitor_id: uuid.UUID,
    actor: User,
    ip_address: str | None,
) -> Visitor:
    visitor = get_or_404(db, visitor_id, for_update=True)
    visitor.is_active = False
    for profile in visitor.face_profiles:
        if profile.is_active:
            profile.is_active = False
            profile.active_profile_key = None
            profile.updated_at = utcnow()
    audit_service.record(
        db,
        action="VISITOR_DEACTIVATED",
        entity_type="visitor",
        entity_id=visitor.id,
        description="Visitor soft-deleted/deactivated; biometric processing disabled",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(visitor)
    return visitor


def withdraw_biometric_consent(
    db: Session,
    *,
    visitor_id: uuid.UUID,
    reason: str | None,
    policy_version: str | None,
    actor: User,
    ip_address: str | None,
) -> Visitor:
    visitor = get_or_404(db, visitor_id, for_update=True)
    now = utcnow()
    consent_repo.add(
        db,
        ConsentRecord(
            visitor_id=visitor.id,
            consent_type=ConsentType.BIOMETRIC_PROCESSING,
            policy_version=policy_version or "withdrawal",
            consent_status=ConsentStatus.WITHDRAWN,
            withdrawn_at=now,
            recorded_by=actor.id,
        ),
    )
    for profile in visitor.face_profiles:
        if profile.is_active:
            profile.is_active = False
            profile.active_profile_key = None
            profile.updated_at = now
    audit_service.record(
        db,
        action="BIOMETRIC_CONSENT_WITHDRAWN",
        entity_type="visitor",
        entity_id=visitor.id,
        description=(reason or "Biometric processing consent withdrawn")[:1000],
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(visitor)
    return visitor


def delete_biometric_data(
    db: Session,
    *,
    visitor_id: uuid.UUID,
    reason: str,
    actor: User,
    ip_address: str | None,
) -> Visitor:
    visitor = get_or_404(db, visitor_id, for_update=True)
    now = utcnow()
    deleted = 0
    for profile in visitor.face_profiles:
        if profile.embedding_data is not None or profile.is_active:
            profile.embedding_data = None
            profile.is_active = False
            profile.active_profile_key = None
            profile.deleted_at = now
            profile.deletion_reason = reason[:255]
            profile.updated_at = now
            deleted += 1
    consent_repo.add(
        db,
        ConsentRecord(
            visitor_id=visitor.id,
            consent_type=ConsentType.BIOMETRIC_PROCESSING,
            policy_version="biometric-deletion",
            consent_status=ConsentStatus.WITHDRAWN,
            withdrawn_at=now,
            recorded_by=actor.id,
        ),
    )
    audit_service.record(
        db,
        action="BIOMETRIC_DATA_DELETED",
        entity_type="visitor",
        entity_id=visitor.id,
        description=f"Deleted biometric data from {deleted} face profile(s): {reason}"[:1000],
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(visitor)
    return visitor


def face_profile_out(profile: FaceProfile) -> dict:
    return {
        "id": profile.id,
        "visitor_id": profile.visitor_id,
        "model_version": profile.model_version,
        "embedding_version": profile.embedding_version,
        "is_active": profile.is_active,
        "enrolled_at": profile.enrolled_at,
        "updated_at": profile.updated_at,
        "deleted_at": profile.deleted_at,
    }
