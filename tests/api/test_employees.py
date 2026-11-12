from __future__ import annotations


async def test_employee_crud_and_duplicates(client, admin_headers):
    created = await client.post(
        "/api/v1/employees",
        headers=admin_headers,
        json={
            "employee_code": "EMP-100",
            "full_name": "Jane Host",
            "department": "HR",
            "email": "jane.host@example.com",
            "phone_number": "081211112222",
        },
    )
    assert created.status_code == 201, created.text
    employee = created.json()["data"]

    duplicate_code = await client.post(
        "/api/v1/employees",
        headers=admin_headers,
        json={"employee_code": "EMP-100", "full_name": "Other"},
    )
    assert duplicate_code.status_code == 409
    assert duplicate_code.json()["error_code"] == "EMPLOYEE_CODE_EXISTS"

    duplicate_email = await client.post(
        "/api/v1/employees",
        headers=admin_headers,
        json={
            "employee_code": "EMP-101",
            "full_name": "Other",
            "email": "JANE.HOST@example.com",
        },
    )
    assert duplicate_email.status_code == 409
    assert duplicate_email.json()["error_code"] == "EMPLOYEE_EMAIL_EXISTS"

    listed = await client.get("/api/v1/employees?search=Jane", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    fetched = await client.get(f"/api/v1/employees/{employee['id']}", headers=admin_headers)
    assert fetched.status_code == 200

    updated = await client.put(
        f"/api/v1/employees/{employee['id']}",
        headers=admin_headers,
        json={"department": "People Operations"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["department"] == "People Operations"

    deactivated = await client.delete(
        f"/api/v1/employees/{employee['id']}", headers=admin_headers
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False

    missing = await client.get(
        "/api/v1/employees/00000000-0000-0000-0000-000000000000", headers=admin_headers
    )
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "EMPLOYEE_NOT_FOUND"


async def test_viewer_cannot_manage_employees(client, viewer_headers):
    listed = await client.get("/api/v1/employees", headers=viewer_headers)
    assert listed.status_code == 403
    created = await client.post(
        "/api/v1/employees",
        headers=viewer_headers,
        json={"employee_code": "EMP-X", "full_name": "Nope"},
    )
    assert created.status_code == 403
