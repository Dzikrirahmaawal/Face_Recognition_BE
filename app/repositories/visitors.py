from __future__ import annotations

import uuid

from sqlalchemy import false, or_, select, true
from sqlalchemy.orm import Session, selectinload

from app.models.visitor import FaceProfile, Visitor


def get(db: Session, visitor_id: uuid.UUID, for_update: bool = False) -> Visitor | None:
    stmt = select(Visitor).where(Visitor.id == visitor_id).options(selectinload(Visitor.face_profiles))
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def get_by_code(db: Session, code: str) -> Visitor | None:
    return db.scalars(select(Visitor).where(Visitor.visitor_code == code)).first()


def list_visitors(
    db: Session,
    page: int,
    page_size: int,
    search: str | None = None,
    is_active: bool | None = None,
):
    stmt = select(Visitor).options(selectinload(Visitor.face_profiles)).order_by(Visitor.created_at.desc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Visitor.full_name.ilike(like),
                Visitor.visitor_code.ilike(like),
                Visitor.company_name.ilike(like),
                Visitor.phone_number.ilike(like),
                Visitor.email.ilike(like),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Visitor.is_active.is_(is_active))
    return stmt


def add(db: Session, visitor: Visitor) -> Visitor:
    db.add(visitor)
    return visitor


def add_face_profile(db: Session, profile: FaceProfile) -> FaceProfile:
    db.add(profile)
    return profile


def get_face_profile(db: Session, profile_id: uuid.UUID) -> FaceProfile | None:
    return db.get(FaceProfile, profile_id)


def list_active_profiles(db: Session, model_version: str, embedding_version: str) -> list[FaceProfile]:
    stmt = (
        select(FaceProfile)
        .where(
            FaceProfile.is_active == true(),
            FaceProfile.embedding_data.is_not(None),
            FaceProfile.model_version == model_version,
            FaceProfile.embedding_version == embedding_version,
        )
        .options(selectinload(FaceProfile.visitor))
    )
    return list(db.scalars(stmt).all())


def get_active_profile_for_visitor(db: Session, visitor_id: uuid.UUID) -> FaceProfile | None:
    stmt = select(FaceProfile).where(
        FaceProfile.visitor_id == visitor_id,
        FaceProfile.is_active == true(),
        FaceProfile.embedding_data.is_not(None),
    )
    return db.scalars(stmt).first()


def get_active_profile_by_visitor_for_update(db: Session, visitor_id: uuid.UUID) -> FaceProfile | None:
    stmt = (
        select(FaceProfile)
        .where(
            FaceProfile.visitor_id == visitor_id,
            FaceProfile.is_active == true(),
            FaceProfile.embedding_data.is_not(None),
        )
        .with_for_update()
    )
    return db.scalars(stmt).first()
