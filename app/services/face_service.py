from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.types import utcnow
from app.face_engine.crypto import BiometricCipher
from app.face_engine.detection import validate_single_face
from app.face_engine.factory import get_face_provider, get_liveness_provider
from app.face_engine.interfaces import EnrolledProfile
from app.models.consent import ConsentRecord
from app.models.enums import ConsentStatus, ConsentType, MatchStatus
from app.models.visitor import FaceProfile
from app.repositories import consent as consent_repo
from app.repositories import visitors as visitors_repo
from app.repositories import visits as visits_repo
from app.schemas.visitor import VisitorCreate
from app.services import audit_service, visitor_service
from app.utils.images import decode_image


def _confidence(value: float) -> Decimal:
    return Decimal(str(round(float(value), 4))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _visitor_summary(visitor) -> dict:  # noqa: ANN001
    return {
        "id": visitor.id,
        "visitor_code": visitor.visitor_code,
        "full_name": visitor.full_name,
        "company_name": visitor.company_name,
    }


def _prepare_capture(image_bytes: bytes, content_type: str | None):
    provider = get_face_provider()
    liveness_provider = get_liveness_provider()
    image = decode_image(image_bytes, content_type)
    faces = provider.detect_faces(image)
    face = validate_single_face(faces)
    quality = provider.validate_face_quality(image, face)
    if not quality.acceptable:
        raise ValidationAppError(
            "Face image did not pass quality checks",
            error_code="FACE_QUALITY_REJECTED",
            details={"issues": quality.issues},
        )
    liveness = liveness_provider.verify_liveness(image)
    if not liveness.passed:
        raise ValidationAppError(
            "Liveness verification failed",
            error_code="LIVENESS_FAILED",
            details={"provider": liveness.provider, "reason": liveness.reason},
        )
    embedding = provider.generate_embedding(image, face)
    return image, embedding, quality, liveness


def enroll(
    db: Session,
    *,
    image_bytes: bytes,
    content_type: str | None,
    visitor_id: uuid.UUID | None,
    full_name: str | None,
    identity_number: str | None,
    company_name: str | None,
    phone_number: str | None,
    email: str | None,
    consent_granted: bool,
    consent_policy_version: str,
    replace_existing: bool,
    actor,
    ip_address: str | None,
) -> dict:
    if not consent_granted:
        raise ValidationAppError(
            "Biometric processing consent is required before enrollment",
            error_code="CONSENT_REQUIRED",
        )

    _image, embedding, _quality, _liveness = _prepare_capture(image_bytes, content_type)
    provider = get_face_provider()
    cipher = BiometricCipher()
    now = utcnow()

    if visitor_id is not None:
        visitor = visitor_service.get_or_404(db, visitor_id, for_update=True)
        if not visitor.is_active:
            raise ConflictError("Visitor is inactive", error_code="VISITOR_INACTIVE")
        existing = visitors_repo.get_active_profile_for_visitor(db, visitor.id)
        if existing is not None:
            if not replace_existing:
                raise ConflictError(
                    "Visitor already has an active face profile",
                    error_code="FACE_PROFILE_EXISTS",
                )
            existing.is_active = False
            existing.active_profile_key = None
            existing.updated_at = now
    else:
        if not full_name or not full_name.strip():
            raise ValidationAppError(
                "full_name is required when creating a new visitor during enrollment",
                error_code="VISITOR_NAME_REQUIRED",
            )
        visitor = visitor_service.create_visitor(
            db,
            data=VisitorCreate(
                full_name=full_name.strip(),
                identity_number=identity_number,
                company_name=company_name,
                phone_number=phone_number,
                email=email,
            ),
            actor=actor.user if actor else None,
            ip_address=ip_address,
            commit=False,
        )

    profiles = visitors_repo.list_active_profiles(db, provider.model_version, provider.embedding_version)
    for profile in profiles:
        if profile.visitor_id == visitor.id:
            continue
        other_embedding = cipher.decrypt_embedding(profile.embedding_data)
        if other_embedding is None:
            continue
        similarity = provider.compare_embeddings(embedding, other_embedding)
        if similarity >= settings.FACE_DUPLICATE_THRESHOLD:
            db.rollback()
            other_visitor = visitors_repo.get(db, profile.visitor_id)
            raise ConflictError(
                "A very similar face profile already exists. Manual review is required.",
                error_code="FACE_DUPLICATE_DETECTED",
                details={
                    "review_required": True,
                    "matched_visitor_id": str(profile.visitor_id),
                    "matched_visitor_code": other_visitor.visitor_code if other_visitor else None,
                    "matched_visitor_name": other_visitor.full_name if other_visitor else None,
                    "similarity": round(float(similarity), 4),
                },
            )

    profile = FaceProfile(
        visitor_id=visitor.id,
        embedding_data=cipher.encrypt_embedding(embedding),
        model_version=provider.model_version,
        embedding_version=provider.embedding_version,
        is_active=True,
        active_profile_key=visitor.id,
        enrolled_at=now,
        updated_at=now,
    )
    visitors_repo.add_face_profile(db, profile)
    consent_repo.add(
        db,
        ConsentRecord(
            visitor_id=visitor.id,
            consent_type=ConsentType.BIOMETRIC_PROCESSING,
            policy_version=consent_policy_version,
            consent_status=ConsentStatus.GRANTED,
            consented_at=now,
            recorded_by=actor.user_id if actor else None,
        ),
    )
    audit_service.record(
        db,
        action="FACE_ENROLLED",
        entity_type="visitor",
        entity_id=visitor.id,
        description=f"Face profile enrolled with provider={provider.name} model={provider.model_version}",
        user_id=actor.user_id if actor else None,
        ip_address=ip_address,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Face enrollment conflicted with another profile. Please retry.",
            error_code="FACE_PROFILE_CONFLICT",
        ) from exc
    db.refresh(visitor)
    db.refresh(profile)
    return {
        "visitor": _visitor_summary(visitor),
        "profile_id": profile.id,
        "model_version": profile.model_version,
        "embedding_version": profile.embedding_version,
        "consent_recorded": True,
        "duplicate_review": False,
    }


def identify(
    db: Session,
    *,
    image_bytes: bytes,
    content_type: str | None,
    actor,
    ip_address: str | None,
) -> dict:
    _image, embedding, _quality, _liveness = _prepare_capture(image_bytes, content_type)
    provider = get_face_provider()
    cipher = BiometricCipher()
    profiles = visitors_repo.list_active_profiles(db, provider.model_version, provider.embedding_version)
    enrolled: list[EnrolledProfile] = []
    for profile in profiles:
        decoded = cipher.decrypt_embedding(profile.embedding_data)
        if decoded is None:
            continue
        if not consent_repo.is_biometric_authorized(db, profile.visitor_id):
            continue
        if profile.visitor is None or not profile.visitor.is_active:
            continue
        enrolled.append(
            EnrolledProfile(profile_id=profile.id, visitor_id=profile.visitor_id, embedding=decoded)
        )

    outcome = provider.identify_face(
        embedding,
        enrolled,
        match_threshold=settings.FACE_MATCH_THRESHOLD,
        review_threshold=settings.FACE_REVIEW_THRESHOLD,
        ambiguity_margin=settings.FACE_AMBIGUITY_MARGIN,
    )
    result: dict = {
        "match_status": MatchStatus(outcome.status),
        "visitor": None,
        "confidence": None,
        "review_required": outcome.ambiguous or outcome.status == "REVIEW_REQUIRED",
        "active_visit_id": None,
        "active_visit_status": None,
    }
    if outcome.best is not None:
        visitor = visitors_repo.get(db, outcome.best.visitor_id)
        if visitor is not None:
            result["visitor"] = _visitor_summary(visitor)
            result["confidence"] = _confidence(outcome.best.similarity)
            active = visits_repo.get_active_for_visitor(db, visitor.id)
            if active is not None:
                result["active_visit_id"] = active.id
                result["active_visit_status"] = active.visit_status.value
    audit_service.record(
        db,
        action="FACE_IDENTIFIED",
        entity_type="visitor",
        entity_id=outcome.best.visitor_id if outcome.best else None,
        description=f"Face identification result: {outcome.status}",
        user_id=actor.user_id if actor else None,
        ip_address=ip_address,
    )
    db.commit()
    return result


def verify(
    db: Session,
    *,
    image_bytes: bytes,
    content_type: str | None,
    visitor_id: uuid.UUID,
    actor,
    ip_address: str | None,
) -> dict:
    visitor = visitor_service.get_or_404(db, visitor_id)
    if not visitor.is_active:
        raise ConflictError("Visitor is inactive", error_code="VISITOR_INACTIVE")
    if not consent_repo.is_biometric_authorized(db, visitor.id):
        raise ConflictError(
            "Biometric processing is not authorized for this visitor",
            error_code="BIOMETRIC_AUTHORIZATION_REQUIRED",
        )
    profile = visitors_repo.get_active_profile_for_visitor(db, visitor.id)
    if profile is None or profile.embedding_data is None:
        raise NotFoundError("Active face profile not found", error_code="FACE_PROFILE_NOT_FOUND")

    _image, embedding, _quality, _liveness = _prepare_capture(image_bytes, content_type)
    provider = get_face_provider()
    stored = BiometricCipher().decrypt_embedding(profile.embedding_data)
    similarity = provider.compare_embeddings(embedding, stored) if stored is not None else 0.0
    matched = similarity >= settings.FACE_MATCH_THRESHOLD
    audit_service.record(
        db,
        action="FACE_VERIFIED",
        entity_type="visitor",
        entity_id=visitor.id,
        description=f"Face verification matched={matched}",
        user_id=actor.user_id if actor else None,
        ip_address=ip_address,
    )
    db.commit()
    return {
        "matched": matched,
        "confidence": _confidence(similarity),
        "visitor_id": visitor.id,
    }


def test_liveness(
    db: Session,
    *,
    image_bytes: bytes,
    content_type: str | None,
    actor,
    ip_address: str | None,
) -> dict:
    provider = get_face_provider()
    liveness_provider = get_liveness_provider()
    image = decode_image(image_bytes, content_type)
    faces = provider.detect_faces(image)
    face = validate_single_face(faces)
    quality = provider.validate_face_quality(image, face)
    if not quality.acceptable:
        raise ValidationAppError(
            "Face image did not pass quality checks",
            error_code="FACE_QUALITY_REJECTED",
            details={"issues": quality.issues},
        )
    liveness = liveness_provider.verify_liveness(image)
    audit_service.record(
        db,
        action="LIVENESS_TESTED",
        entity_type="kiosk",
        entity_id=actor.kiosk_id if actor else None,
        description=f"Liveness provider={liveness.provider} passed={liveness.passed}",
        user_id=actor.user_id if actor else None,
        ip_address=ip_address,
    )
    db.commit()
    return {
        "passed": liveness.passed,
        "score": _confidence(liveness.score) if liveness.score is not None else None,
        "provider": liveness.provider,
    }


def delete_profile(
    db: Session,
    *,
    profile_id: uuid.UUID,
    delete_biometrics: bool,
    reason: str,
    actor,
    ip_address: str | None,
) -> dict:
    profile = visitors_repo.get_face_profile(db, profile_id)
    if profile is None:
        raise NotFoundError("Face profile not found", error_code="FACE_PROFILE_NOT_FOUND")
    now = utcnow()
    if delete_biometrics:
        profile.embedding_data = None
        profile.deleted_at = now
        profile.deletion_reason = reason[:255]
    profile.is_active = False
    profile.active_profile_key = None
    profile.updated_at = now
    audit_service.record(
        db,
        action="FACE_PROFILE_DELETED" if delete_biometrics else "FACE_PROFILE_DEACTIVATED",
        entity_type="face_profile",
        entity_id=profile.id,
        description=(
            f"Biometric embedding deleted. Reason: {reason}"
            if delete_biometrics
            else "Face profile deactivated"
        )[:1000],
        user_id=actor.user_id if actor else None,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(profile)
    return visitor_service.face_profile_out(profile)
