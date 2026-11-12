from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.security import hash_password, validate_password_strength
from app.models.user import User
from app.repositories import users as users_repo
from app.repositories.base import paginate
from app.schemas.admin import UserUpdate
from app.services import audit_service


def get_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = users_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found", error_code="USER_NOT_FOUND")
    return user


def list_users(db: Session, *, page: int, page_size: int, role: str | None, is_active: bool | None):
    stmt = users_repo.list_users(db, page, page_size, role=role, is_active=is_active)
    return paginate(db, stmt, page, page_size)


def update_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    data: UserUpdate,
    actor: User,
    ip_address: str | None,
) -> User:
    user = get_or_404(db, user_id)
    changes = data.model_dump(exclude_unset=True)
    revoke_tokens = False
    if "email" in changes and changes["email"] is not None:
        email = str(changes["email"]).lower()
        existing = users_repo.get_by_email(db, email)
        if existing is not None and existing.id != user.id:
            raise ConflictError("Email is already in use", error_code="EMAIL_EXISTS")
        changes["email"] = email
    if "password" in changes and changes["password"] is not None:
        errors = validate_password_strength(changes["password"])
        if errors:
            raise ValidationAppError("Password does not meet security requirements", details=errors)
        user.password_hash = hash_password(changes["password"])
        del changes["password"]
        revoke_tokens = True
    if "role" in changes and changes["role"] != user.role:
        revoke_tokens = True
    if "is_active" in changes and changes["is_active"] != user.is_active:
        revoke_tokens = True
    for field, value in changes.items():
        setattr(user, field, value)
    if revoke_tokens:
        user.token_version += 1
        from app.core.types import utcnow

        users_repo.revoke_all_refresh_tokens(db, user.id, utcnow())
    audit_service.record(
        db,
        action="USER_UPDATED",
        entity_type="user",
        entity_id=user.id,
        description=f"Fields updated: {', '.join(sorted(changes.keys()))}",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return user
