from __future__ import annotations

from tests.helpers import enroll_visitor, make_face_image


async def _manual_visitor(client, admin_headers) -> dict:
    response = await client.post(
        "/api/v1/visitors",
        headers=admin_headers,
        json={"full_name": "Manual Visitor", "phone_number": "081299999999"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_check_in_check_out_and_duplicates(client, kiosk_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=21)
    visitor_id = enrolled["visitor"]["id"]

    check_in = await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE", "confidence_score": 0.93},
    )
    assert check_in.status_code == 201, check_in.text
    data = check_in.json()["data"]
    assert data["event_type"] == "CHECK_IN"
    assert data["visit_status"] == "CHECKED_IN"

    duplicate_in = await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    assert duplicate_in.status_code == 409
    assert duplicate_in.json()["error_code"] == "ALREADY_CHECKED_IN"

    check_out = await client.post(
        "/api/v1/attendance/check-out",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    assert check_out.status_code == 200, check_out.text
    assert check_out.json()["data"]["event_type"] == "CHECK_OUT"
    assert check_out.json()["data"]["visit_status"] == "CHECKED_OUT"

    duplicate_out = await client.post(
        "/api/v1/attendance/check-out",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    assert duplicate_out.status_code == 409
    assert duplicate_out.json()["error_code"] == "NO_ACTIVE_VISIT"


async def test_manual_non_biometric_fallback(client, admin_headers, kiosk_headers):
    visitor = await _manual_visitor(client, admin_headers)
    response = await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor["id"], "method": "MANUAL"},
    )
    assert response.status_code == 201
    checkout = await client.post(
        "/api/v1/attendance/check-out",
        headers=kiosk_headers,
        json={"visitor_id": visitor["id"], "method": "MANUAL"},
    )
    assert checkout.status_code == 200


async def test_check_in_without_active_visit_for_checkout(client, kiosk_headers, admin_headers):
    visitor = await _manual_visitor(client, admin_headers)
    response = await client.post(
        "/api/v1/attendance/check-out",
        headers=kiosk_headers,
        json={"visitor_id": visitor["id"], "method": "MANUAL"},
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "NO_ACTIVE_VISIT"


async def test_idempotent_check_in_and_check_out(client, kiosk_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=33)
    visitor_id = enrolled["visitor"]["id"]
    headers = {**kiosk_headers, "Idempotency-Key": "checkin-key-001"}
    body = {"visitor_id": visitor_id, "method": "FACE"}

    first = await client.post("/api/v1/attendance/check-in", headers=headers, json=body)
    second = await client.post("/api/v1/attendance/check-in", headers=headers, json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["attendance_id"] == second.json()["data"]["attendance_id"]

    checkout_headers = {**kiosk_headers, "Idempotency-Key": "checkout-key-001"}
    out_first = await client.post("/api/v1/attendance/check-out", headers=checkout_headers, json=body)
    out_second = await client.post("/api/v1/attendance/check-out", headers=checkout_headers, json=body)
    assert out_first.status_code == 200
    assert out_second.status_code == 200
    assert out_first.json()["data"]["attendance_id"] == out_second.json()["data"]["attendance_id"]

    conflict = await client.post(
        "/api/v1/attendance/check-in",
        headers={**kiosk_headers, "Idempotency-Key": "checkin-key-001"},
        json={"visitor_id": visitor_id, "method": "MANUAL"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_consent_withdrawal_blocks_biometric_attendance(client, kiosk_headers, admin_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=55)
    visitor_id = enrolled["visitor"]["id"]

    withdraw = await client.post(
        f"/api/v1/visitors/{visitor_id}/biometric/withdraw",
        headers=admin_headers,
        json={"reason": "Visitor requested withdrawal", "policy_version": "1.1"},
    )
    assert withdraw.status_code == 200

    identify = await client.post(
        "/api/v1/face/identify",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(55), "image/png")},
    )
    assert identify.status_code == 200
    assert identify.json()["data"]["match_status"] == "UNKNOWN"

    blocked = await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error_code"] == "BIOMETRIC_AUTHORIZATION_REQUIRED"

    manual = await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "MANUAL"},
    )
    assert manual.status_code == 201


async def test_biometric_deletion_retains_attendance_history(client, kiosk_headers, admin_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=61)
    visitor_id = enrolled["visitor"]["id"]
    await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    deleted = await client.request(
        "DELETE",
        f"/api/v1/visitors/{visitor_id}/biometric",
        headers=admin_headers,
        json={"reason": "Retention deletion request", "delete_face_profiles": True},
    )
    assert deleted.status_code == 200
    history = await client.get(f"/api/v1/attendance?visitor_id={visitor_id}", headers=admin_headers)
    assert history.status_code == 200
    assert history.json()["meta"]["total"] == 1


async def test_unknown_visitor_and_unauthorized_kiosk(client, admin_headers):
    missing = await client.post(
        "/api/v1/attendance/check-in",
        headers=admin_headers,
        json={"visitor_id": "00000000-0000-0000-0000-000000000000", "method": "MANUAL"},
    )
    assert missing.status_code == 404

    unauthorized = await client.post(
        "/api/v1/attendance/check-in",
        headers={"X-Kiosk-Token": "nope"},
        json={"visitor_id": "00000000-0000-0000-0000-000000000000", "method": "MANUAL"},
    )
    assert unauthorized.status_code == 401


async def test_attendance_correction_is_append_only(client, kiosk_headers, admin_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=71)
    visitor_id = enrolled["visitor"]["id"]
    check_in = await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    attendance_id = check_in.json()["data"]["attendance_id"]
    correction = await client.post(
        f"/api/v1/admin/attendance/{attendance_id}/correct",
        headers=admin_headers,
        json={
            "corrected_event_type": "CHECK_IN",
            "corrected_timestamp": "2026-01-01T08:00:00Z",
            "reason": "Clock was wrong",
        },
    )
    assert correction.status_code == 200, correction.text
    assert correction.json()["data"]["is_correction"] is True
    assert correction.json()["data"]["correction_of_id"] == attendance_id

    listed = await client.get(f"/api/v1/attendance?visitor_id={visitor_id}", headers=admin_headers)
    assert listed.json()["meta"]["total"] == 2
