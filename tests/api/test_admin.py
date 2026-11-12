from __future__ import annotations


async def test_user_lifecycle_and_token_revocation(client, admin_headers):
    created = await client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "reception",
            "email": "reception@example.com",
            "password": "ReceptionPass123!",
            "full_name": "Front Desk",
            "role": "RECEPTIONIST",
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()["data"]
    assert user["role"] == "RECEPTIONIST"

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "reception", "password": "ReceptionPass123!"},
    )
    assert login.status_code == 200
    user_token = login.json()["data"]["tokens"]["access_token"]

    updated = await client.patch(
        f"/api/v1/admin/users/{user['id']}",
        headers=admin_headers,
        json={"role": "SECURITY", "password": "NewReceptionPass123!"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["role"] == "SECURITY"

    revoked = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert revoked.status_code == 401
    assert revoked.json()["error_code"] == "TOKEN_REVOKED"

    old_password = await client.post(
        "/api/v1/auth/login",
        json={"username": "reception", "password": "ReceptionPass123!"},
    )
    assert old_password.status_code == 401

    new_password = await client.post(
        "/api/v1/auth/login",
        json={"username": "reception", "password": "NewReceptionPass123!"},
    )
    assert new_password.status_code == 200


async def test_duplicate_user_and_weak_password(client, admin_headers):
    payload = {
        "username": "duplicate",
        "email": "duplicate@example.com",
        "password": "ValidPassword123!",
        "full_name": "Duplicate",
        "role": "VIEWER",
    }
    first = await client.post("/api/v1/admin/users", headers=admin_headers, json=payload)
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={**payload, "email": "other@example.com"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "USERNAME_EXISTS"

    weak = await client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={**payload, "username": "weak", "email": "weak@example.com", "password": "weakpassword"},
    )
    assert weak.status_code == 422
    assert weak.json()["error_code"] == "VALIDATION_ERROR"


async def test_viewer_cannot_manage_users_or_read_audit(client, viewer_headers):
    users = await client.get("/api/v1/admin/users", headers=viewer_headers)
    assert users.status_code == 403
    audit = await client.get("/api/v1/admin/audit-logs", headers=viewer_headers)
    assert audit.status_code == 403


async def test_audit_logs_record_actions(client, admin_headers):
    await client.post(
        "/api/v1/visitors",
        headers=admin_headers,
        json={"full_name": "Audited Visitor"},
    )
    logs = await client.get(
        "/api/v1/admin/audit-logs?action=VISITOR_CREATED", headers=admin_headers
    )
    assert logs.status_code == 200
    assert logs.json()["meta"]["total"] == 1
    entry = logs.json()["data"][0]
    assert entry["action"] == "VISITOR_CREATED"
    assert entry["entity_type"] == "visitor"
    assert entry["description"]
