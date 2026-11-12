from __future__ import annotations

import uuid
from datetime import datetime, timezone

import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError, ValidationAppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_hash,
    verify_password,
)
from app.core.types import ensure_utc, utcnow
from app.models.enums import UserRole
from app.models.user import RefreshToken, User
from app.repositories import users as users_repo
from app.services import audit_service


def _token_response(db: Session, user: User, *, ip_address: str | None, user_agent: str | None) -> dict:
    access_token = create_access_token(user.id, user.role.value, user.token_version)
    refresh_token, claims = create_refresh_token(user.id, user.role.value, user.token_version)
    expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=timezone.utc)
    stored = RefreshToken(
        user_id=user.id,
        token_hash=token_hash(refresh_token),
        jti=uuid.UUID(claims["jti"]),
        expires_at=expires_at,
        created_at=utcnow(),
        ip_address=(ip_address or "")[:45] or None,
        user_agent=(user_agent or "")[:255] or None,
    )
    users_repo.add_refresh_token(db, stored)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def login(
    db: Session,
    *,
    username: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, dict]:
    user = users_repo.get_by_username_or_email(db, username.strip())
    if user is None or not verify_password(password, user.password_hash):
        audit_service.record(
            db,
            action="LOGIN_FAILED",
            entity_type="user",
            entity_id=username,
            description="Failed login attempt",
            ip_address=ip_address,
        )
        db.commit()
        raise AuthenticationError("Invalid username or password", error_code="INVALID_CREDENTIALS")
    if not user.is_active:
        audit_service.record(
            db,
            action="LOGIN_FAILED",
            entity_type="user",
            entity_id=user.id,
            description="Login attempt on inactive account",
            user_id=user.id,
            ip_address=ip_address,
        )
        db.commit()
        raise AuthenticationError("Account is disabled", error_code="ACCOUNT_DISABLED")

    user.last_login_at = utcnow()
    tokens = _token_response(db, user, ip_address=ip_address, user_agent=user_agent)
    audit_service.record(
        db,
        action="LOGIN_SUCCESS",
        entity_type="user",
        entity_id=user.id,
        description="User logged in",
        user_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return user, tokens


def refresh(
    db: Session,
    *,
    refresh_token: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, dict]:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = uuid.UUID(str(payload["sub"]))
        jti = uuid.UUID(str(payload["jti"]))
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise AuthenticationError("Invalid refresh token", error_code="INVALID_REFRESH_TOKEN") from exc

    stored = users_repo.get_refresh_token_by_hash(db, token_hash(refresh_token))
    if stored is None or stored.user_id != user_id or stored.jti != jti:
        raise AuthenticationError("Invalid refresh token", error_code="INVALID_REFRESH_TOKEN")

    user = users_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account is not available", error_code="ACCOUNT_DISABLED")

    if stored.revoked_at is not None:
        # Refresh token reuse indicates possible theft. Revoke the whole family.
        user.token_version += 1
        users_repo.revoke_all_refresh_tokens(db, user.id, utcnow())
        audit_service.record(
            db,
            action="REFRESH_TOKEN_REUSE_DETECTED",
            entity_type="user",
            entity_id=user.id,
            description="Revoked all sessions after refresh token reuse",
            user_id=user.id,
            ip_address=ip_address,
        )
        db.commit()
        raise AuthenticationError("Refresh token has already been used", error_code="REFRESH_TOKEN_REUSED")

    expires_at = ensure_utc(stored.expires_at)
    if expires_at is None or expires_at < utcnow():
        raise AuthenticationError("Refresh token has expired", error_code="REFRESH_TOKEN_EXPIRED")

    if int(payload.get("tv", -1)) != user.token_version:
        raise AuthenticationError("Refresh token is no longer valid", error_code="TOKEN_REVOKED")

    tokens = _token_response(db, user, ip_address=ip_address, user_agent=user_agent)
    new_stored = users_repo.get_refresh_token_by_hash(db, token_hash(tokens["refresh_token"]))
    stored.revoked_at = utcnow()
    stored.replaced_by_id = new_stored.id if new_stored else None
    audit_service.record(
        db,
        action="TOKEN_REFRESHED",
        entity_type="user",
        entity_id=user.id,
        description="Refresh token rotated",
        user_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return user, tokens


def logout(
    db: Session,
    *,
    user: User,
    refresh_token: str | None,
    all_devices: bool,
    ip_address: str | None,
) -> None:
    now = utcnow()
    if all_devices:
        user.token_version += 1
        users_repo.revoke_all_refresh_tokens(db, user.id, now)
    elif refresh_token:
        stored = users_repo.get_refresh_token_by_hash(db, token_hash(refresh_token))
        if stored is not None and stored.user_id == user.id and stored.revoked_at is None:
            stored.revoked_at = now
    audit_service.record(
        db,
        action="LOGOUT",
        entity_type="user",
        entity_id=user.id,
        description="All sessions revoked" if all_devices else "Session revoked",
        user_id=user.id,
        ip_address=ip_address,
    )
    db.commit()


def create_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    full_name: str,
    role: UserRole,
    actor: User | None,
    ip_address: str | None,
) -> User:
    from app.core.security import validate_password_strength

    errors = validate_password_strength(password)
    if errors:
        raise ValidationAppError("Password does not meet security requirements", details=errors)
    if users_repo.get_by_username(db, username):
        raise ConflictError("Username is already in use", error_code="USERNAME_EXISTS")
    if users_repo.get_by_email(db, email):
        raise ConflictError("Email is already in use", error_code="EMAIL_EXISTS")
    user = User(
        username=username,
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True,
    )
    users_repo.add(db, user)
    db.flush()
    audit_service.record(
        db,
        action="USER_CREATED",
        entity_type="user",
        entity_id=user.id,
        description=f"Created user {username} with role {getattr(role, 'value', role)}",
        user_id=actor.id if actor else None,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return user
