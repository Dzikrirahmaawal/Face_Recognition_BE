from __future__ import annotations

from tests.helpers import enroll_visitor


async def _visitor(client, admin_headers, name: str = "Visit Visitor") -> dict:
    response = await client.post("/api/v1/visitors", headers=admin_headers, json={"full_name": name})
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _employee(client, admin_headers) -> dict:
    response = await client.post(
        "/api/v1/employees",
        headers=admin_headers,
        json={
            "employee_code": "EMP-001",
            "full_name": "Host Employee",
            "department": "Operations",
            "email": "host@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_visit_lifecycle(client, admin_headers):
    visitor = await _visitor(client, admin_headers)
    employee = await _employee(client, admin_headers)

    created = await client.post(
        "/api/v1/visits",
        headers=admin_headers,
        json={
            "visitor_id": visitor["id"],
            "purpose": "Meeting",
            "host_employee_id": employee["id"],
        },
    )
    assert created.status_code == 201, created.text
    visit = created.json()["data"]
    assert visit["visit_status"] == "WAITING"
    assert visit["visitor"]["full_name"] == "Visit Visitor"

    duplicate = await client.post(
        "/api/v1/visits", headers=admin_headers, json={"visitor_id": visitor["id"]}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "ACTIVE_VISIT_EXISTS"

    fetched = await client.get(f"/api/v1/visits/{visit['id']}", headers=admin_headers)
    assert fetched.status_code == 200

    updated = await client.put(
        f"/api/v1/visits/{visit['id']}",
        headers=admin_headers,
        json={"purpose": "Updated purpose"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["purpose"] == "Updated purpose"

    listed = await client.get("/api/v1/visits?status=WAITING", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    cancelled = await client.post(
        f"/api/v1/visits/{visit['id']}/cancel",
        headers=admin_headers,
        json={"reason": "Visitor did not arrive"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["visit_status"] == "CANCELLED"

    again = await client.post(
        f"/api/v1/visits/{visit['id']}/cancel", headers=admin_headers, json={}
    )
    assert again.status_code == 409
    assert again.json()["error_code"] == "VISIT_ALREADY_CANCELLED"


async def test_cannot_cancel_checked_in_visit(client, admin_headers, kiosk_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=201)
    visitor_id = enrolled["visitor"]["id"]
    visit = await client.post(
        "/api/v1/visits", headers=admin_headers, json={"visitor_id": visitor_id}
    )
    visit_id = visit.json()["data"]["id"]
    check_in = await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "visit_id": visit_id, "method": "FACE"},
    )
    assert check_in.status_code == 201

    cancel = await client.post(
        f"/api/v1/visits/{visit_id}/cancel", headers=admin_headers, json={}
    )
    assert cancel.status_code == 409
    assert cancel.json()["error_code"] == "VISIT_CHECKOUT_REQUIRED"

    await client.post(
        "/api/v1/attendance/check-out",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "visit_id": visit_id, "method": "FACE"},
    )
    after_checkout = await client.post(
        f"/api/v1/visits/{visit_id}/cancel", headers=admin_headers, json={}
    )
    assert after_checkout.status_code == 409
    assert after_checkout.json()["error_code"] == "VISIT_ALREADY_CLOSED"


async def test_inactive_visitor_and_invalid_host(client, admin_headers):
    visitor = await _visitor(client, admin_headers, "Inactive Visit Visitor")
    await client.delete(f"/api/v1/visitors/{visitor['id']}", headers=admin_headers)
    inactive = await client.post(
        "/api/v1/visits", headers=admin_headers, json={"visitor_id": visitor["id"]}
    )
    assert inactive.status_code == 409
    assert inactive.json()["error_code"] == "VISITOR_INACTIVE"

    active_visitor = await _visitor(client, admin_headers, "Host Check Visitor")
    missing_host = await client.post(
        "/api/v1/visits",
        headers=admin_headers,
        json={
            "visitor_id": active_visitor["id"],
            "host_employee_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert missing_host.status_code == 404
    assert missing_host.json()["error_code"] == "HOST_EMPLOYEE_NOT_FOUND"

    employee = await _employee(client, admin_headers)
    await client.delete(f"/api/v1/employees/{employee['id']}", headers=admin_headers)
    inactive_host = await client.post(
        "/api/v1/visits",
        headers=admin_headers,
        json={"visitor_id": active_visitor["id"], "host_employee_id": employee["id"]},
    )
    assert inactive_host.status_code == 409
    assert inactive_host.json()["error_code"] == "HOST_EMPLOYEE_INACTIVE"


async def test_viewer_can_read_visits_but_not_write(client, viewer_headers):
    listed = await client.get("/api/v1/visits", headers=viewer_headers)
    assert listed.status_code == 200
    created = await client.post(
        "/api/v1/visits",
        headers=viewer_headers,
        json={"visitor_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert created.status_code == 403
