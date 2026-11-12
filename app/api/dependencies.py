from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.permissions import Permission, role_has_permission
from app.core.security import decode_token, hash_kiosk_token
from app.core.types import ensure_utc, utcnow
from app.models.kiosk import Kiosk
from app.models.user import User
from app.repositories import kiosks as kiosks_repo
from app.repositories import users as users_repo

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Actor:
    user: User | None = None
    kiosk: Kiosk | None = None
    ip_address: str | None = None

    @property
    def user_id(self) -> uuid.UUID | None:
        return self.user.id if self.user else None

    @property
    def kiosk_id(self) -> uuid.UUID | None:
        return self.kiosk.id if self.kiosk else None

    @property
    def is_kiosk(self) -> bool:
        return self.kiosk is not None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = uuid.UUID(str(payload["sub"]))
        token_version = int(payload.get("tv", -1))
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise AuthenticationError("Invalid or expired access token", error_code="INVALID_TOKEN") from exc

    user = users_repo.get_by_id(db, user_id)
    if user is None:
        raise AuthenticationError("User no longer exists", error_code="INVALID_TOKEN")
    if not user.is_active:
        raise AuthenticationError("Account is disabled", error_code="ACCOUNT_DISABLED")
    if user.token_version != token_version:
        raise AuthenticationError("Token has been revoked", error_code="TOKEN_REVOKED")
    return user


def require_permissions(*permissions: Permission):
    def dependency(user: User = Depends(get_current_user)) -> User:
        for permission in permissions:
            if not role_has_permission(user.role, permission):
                raise PermissionDeniedError(f"Missing permission: {permission.value}")
        return user

    return dependency


def _authenticate_kiosk(db: Session, token: str) -> Kiosk:
    kiosk = kiosks_repo.get_by_token_hash(db, hash_kiosk_token(token))
    if kiosk is None:
        raise AuthenticationError("Invalid kiosk device token", error_code="INVALID_KIOSK_TOKEN")
    if not kiosk.is_active:
        raise AuthenticationError("Kiosk device is disabled", error_code="KIOSK_DISABLED")
    last_seen = ensure_utc(kiosk.last_seen_at)
    now = utcnow()
    if last_seen is None or (now - last_seen).total_seconds() > settings.KIOSK_LAST_SEEN_UPDATE_SECONDS:
        kiosk.last_seen_at = now
    return kiosk


def get_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Actor:
    ip = request.client.host if request.client else None
    kiosk_token = request.headers.get("X-Kiosk-Token")
    if kiosk_token:
        kiosk = _authenticate_kiosk(db, kiosk_token)
        return Actor(kiosk=kiosk, ip_address=ip)
    if credentials is None:
        raise AuthenticationError("Provide a staff bearer token or X-Kiosk-Token")
    user = get_current_user(credentials=credentials, db=db)
    return Actor(user=user, ip_address=ip)


def require_actor(*permissions: Permission, allow_kiosk: bool = True):
    def dependency(request: Request, db: Session = Depends(get_db)) -> Actor:
        ip = request.client.host if request.client else None
        kiosk_token = request.headers.get("X-Kiosk-Token")
        if kiosk_token:
            if not allow_kiosk:
                raise PermissionDeniedError("This endpoint is not available to kiosk devices")
            kiosk = _authenticate_kiosk(db, kiosk_token)
            return Actor(kiosk=kiosk, ip_address=ip)
        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise AuthenticationError("Provide a staff bearer token or X-Kiosk-Token")
        from app.core.security import decode_token as _decode

        try:
            payload = _decode(authorization.split(" ", 1)[1], expected_type="access")
            user_id = uuid.UUID(str(payload["sub"]))
            token_version = int(payload.get("tv", -1))
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise AuthenticationError("Invalid or expired access token", error_code="INVALID_TOKEN") from exc
        user = users_repo.get_by_id(db, user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User is not available", error_code="INVALID_TOKEN")
        if user.token_version != token_version:
            raise AuthenticationError("Token has been revoked", error_code="TOKEN_REVOKED")
        for permission in permissions:
            if not role_has_permission(user.role, permission):
                raise PermissionDeniedError(f"Missing permission: {permission.value}")
        return Actor(user=user, ip_address=ip)

    return dependency
