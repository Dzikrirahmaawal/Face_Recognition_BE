from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import RefreshToken, User


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_username_or_email(db: Session, identifier: str) -> User | None:
    stmt = select(User).where(or_(User.username == identifier, User.email == identifier))
    return db.scalars(stmt).first()


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalars(select(User).where(User.username == username)).first()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email)).first()


def list_users(db: Session, page: int, page_size: int, role: str | None = None, is_active: bool | None = None):
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    return stmt


def add(db: Session, user: User) -> User:
    db.add(user)
    return user


def add_refresh_token(db: Session, token: RefreshToken) -> RefreshToken:
    db.add(token)
    return token


def get_refresh_token_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    return db.scalars(select(RefreshToken).where(RefreshToken.token_hash == token_hash)).first()


def revoke_refresh_token(db: Session, token: RefreshToken, revoked_at: datetime, replaced_by_id: uuid.UUID | None = None):
    token.revoked_at = revoked_at
    token.replaced_by_id = replaced_by_id


def revoke_all_refresh_tokens(db: Session, user_id: uuid.UUID, revoked_at: datetime) -> None:
    stmt = select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    for token in db.scalars(stmt).all():
        token.revoked_at = revoked_at
