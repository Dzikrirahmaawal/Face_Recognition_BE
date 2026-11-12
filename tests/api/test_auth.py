from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserRole


async def test_login_and_me(client, admin_user):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "AdminPassword123!"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["user"]["role"] == "SUPER_ADMIN"
    assert payload["data"]["tokens"]["access_token"]
    assert payload["data"]["tokens"]["refresh_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['data']['tokens']['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "admin"


async def test_login_rejects_bad_password(client, admin_user):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_CREDENTIALS"


async def test_login_rejects_inactive_account(client, db: Session):
    user = User(
        username="disabled",
        email="disabled@example.com",
        password_hash=hash_password("DisabledPassword123!"),
        full_name="Disabled",
        role=UserRole.VIEWER,
        is_active=False,
    )
    db.add(user)
    db.commit()
    response = await client.post(
        "/api/v1/auth/login", json={"username": "disabled", "password": "DisabledPassword123!"}
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "ACCOUNT_DISABLED"


async def test_refresh_rotation_and_reuse_detection(client, admin_user):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "AdminPassword123!"}
    )
    first_refresh = login.json()["data"]["tokens"]["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert refreshed.status_code == 200
    second_refresh = refreshed.json()["data"]["tokens"]["refresh_token"]
    assert second_refresh != first_refresh

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert reused.status_code == 401
    assert reused.json()["error_code"] == "REFRESH_TOKEN_REUSED"

    # Reuse detection revokes the token family.
    after_reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh})
    assert after_reuse.status_code == 401


async def test_logout_all_devices_revokes_access_token(client, admin_tokens):
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    response = await client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": admin_tokens["refresh_token"], "all_devices": True},
    )
    assert response.status_code == 200
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 401
    assert me.json()["error_code"] == "TOKEN_REVOKED"


@pytest.mark.parametrize("path", ["/health", "/ready"])
async def test_health_endpoints(client, path):
    response = await client.get(path)
    assert response.status_code == 200
    assert response.json()["success"] is True
