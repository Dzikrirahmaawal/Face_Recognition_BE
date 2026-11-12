from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, UserOut
from app.schemas.common import success_payload
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip, user_agent = _client_meta(request)
    user, tokens = auth_service.login(
        db,
        username=payload.username,
        password=payload.password,
        ip_address=ip,
        user_agent=user_agent,
    )
    return success_payload(
        data={
            "user": UserOut.model_validate(user).model_dump(mode="json"),
            "tokens": tokens,
        },
        message="Login successful",
    )


@router.post("/refresh")
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    ip, user_agent = _client_meta(request)
    user, tokens = auth_service.refresh(
        db,
        refresh_token=payload.refresh_token,
        ip_address=ip,
        user_agent=user_agent,
    )
    return success_payload(
        data={
            "user": UserOut.model_validate(user).model_dump(mode="json"),
            "tokens": tokens,
        },
        message="Token refreshed",
    )


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ip, _ = _client_meta(request)
    auth_service.logout(
        db,
        user=user,
        refresh_token=payload.refresh_token,
        all_devices=payload.all_devices,
        ip_address=ip,
    )
    return success_payload(message="Logged out successfully")


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return success_payload(
        data=UserOut.model_validate(user).model_dump(mode="json"),
        message="Current user",
    )
