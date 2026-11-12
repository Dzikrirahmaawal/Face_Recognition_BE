from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import Actor, require_actor, require_permissions
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import PayloadTooLargeError, ValidationAppError
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.common import success_payload
from app.services import face_service

router = APIRouter(prefix="/face", tags=["Face Recognition"])


async def _read_upload(file: UploadFile) -> bytes:
    raw = await file.read(settings.MAX_UPLOAD_SIZE + 1)
    if len(raw) > settings.MAX_UPLOAD_SIZE:
        raise PayloadTooLargeError(
            f"Image exceeds the maximum size of {settings.MAX_UPLOAD_SIZE} bytes"
        )
    return raw


@router.post("/enroll", status_code=201)
async def enroll_face(
    image: UploadFile = File(...),
    visitor_id: uuid.UUID | None = Form(None),
    full_name: str | None = Form(None),
    identity_number: str | None = Form(None),
    company_name: str | None = Form(None),
    phone_number: str | None = Form(None),
    email: str | None = Form(None),
    consent_granted: bool = Form(True),
    consent_policy_version: str = Form("1.0"),
    replace_existing: bool = Form(False),
    actor: Actor = Depends(require_actor(Permission.FACE_ENROLL)),
    db: Session = Depends(get_db),
):
    raw = await _read_upload(image)
    result = face_service.enroll(
        db,
        image_bytes=raw,
        content_type=image.content_type,
        visitor_id=visitor_id,
        full_name=full_name,
        identity_number=identity_number,
        company_name=company_name,
        phone_number=phone_number,
        email=email,
        consent_granted=consent_granted,
        consent_policy_version=consent_policy_version,
        replace_existing=replace_existing,
        actor=actor,
        ip_address=actor.ip_address,
    )
    return success_payload(data=result, message="Face enrolled successfully")


@router.post("/identify")
async def identify_face(
    image: UploadFile = File(...),
    actor: Actor = Depends(require_actor(Permission.FACE_IDENTIFY)),
    db: Session = Depends(get_db),
):
    raw = await _read_upload(image)
    result = face_service.identify(
        db,
        image_bytes=raw,
        content_type=image.content_type,
        actor=actor,
        ip_address=actor.ip_address,
    )
    return success_payload(data=result, message="Face identification completed")


@router.post("/verify")
async def verify_face(
    visitor_id: uuid.UUID = Form(...),
    image: UploadFile = File(...),
    actor: Actor = Depends(require_actor(Permission.FACE_VERIFY)),
    db: Session = Depends(get_db),
):
    raw = await _read_upload(image)
    result = face_service.verify(
        db,
        image_bytes=raw,
        content_type=image.content_type,
        visitor_id=visitor_id,
        actor=actor,
        ip_address=actor.ip_address,
    )
    return success_payload(data=result, message="Face verification completed")


@router.post("/liveness")
async def test_liveness(
    image: UploadFile = File(...),
    actor: Actor = Depends(require_actor(Permission.FACE_IDENTIFY)),
    db: Session = Depends(get_db),
):
    raw = await _read_upload(image)
    result = face_service.test_liveness(
        db,
        image_bytes=raw,
        content_type=image.content_type,
        actor=actor,
        ip_address=actor.ip_address,
    )
    return success_payload(data=result, message="Liveness check completed")


@router.delete("/profiles/{profile_id}")
def delete_face_profile(
    profile_id: uuid.UUID,
    delete_biometrics: bool = Query(False),
    reason: str | None = Query(None, max_length=255),
    user: User = Depends(require_permissions(Permission.FACE_DELETE)),
    db: Session = Depends(get_db),
):
    if delete_biometrics and (not reason or len(reason.strip()) < 3):
        raise ValidationAppError(
            "A reason of at least 3 characters is required to delete biometric data",
            error_code="REASON_REQUIRED",
        )
    result = face_service.delete_profile(
        db,
        profile_id=profile_id,
        delete_biometrics=delete_biometrics,
        reason=(reason or "Face profile deactivated"),
        actor=Actor(user=user),
        ip_address=None,
    )
    return success_payload(data=result, message="Face profile updated")
