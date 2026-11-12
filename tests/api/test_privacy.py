from __future__ import annotations

from tests.helpers import enroll_visitor, make_face_image


async def test_consent_records_are_listed(client, kiosk_headers, admin_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=301)
    visitor_id = enrolled["visitor"]["id"]
    response = await client.get(f"/api/v1/visitors/{visitor_id}/consents", headers=admin_headers)
    assert response.status_code == 200
    records = response.json()["data"]
    assert len(records) == 1
    assert records[0]["consent_type"] == "BIOMETRIC_PROCESSING"
    assert records[0]["consent_status"] == "GRANTED"
    assert records[0]["policy_version"] == "1.0"


async def test_withdrawal_is_audited_and_idempotent(client, kiosk_headers, admin_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=302)
    visitor_id = enrolled["visitor"]["id"]
    first = await client.post(
        f"/api/v1/visitors/{visitor_id}/biometric/withdraw",
        headers=admin_headers,
        json={"reason": "First withdrawal", "policy_version": "2.0"},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/visitors/{visitor_id}/biometric/withdraw",
        headers=admin_headers,
        json={"reason": "Second withdrawal", "policy_version": "2.0"},
    )
    assert second.status_code == 200

    consents = await client.get(f"/api/v1/visitors/{visitor_id}/consents", headers=admin_headers)
    statuses = [record["consent_status"] for record in consents.json()["data"]]
    assert "WITHDRAWN" in statuses

    audit = await client.get(
        "/api/v1/admin/audit-logs?action=BIOMETRIC_CONSENT_WITHDRAWN", headers=admin_headers
    )
    assert audit.status_code == 200
    assert audit.json()["meta"]["total"] >= 1

    identify = await client.post(
        "/api/v1/face/identify",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(302), "image/png")},
    )
    assert identify.json()["data"]["match_status"] == "UNKNOWN"


async def test_biometric_deletion_clears_profiles_and_keeps_visitor(client, kiosk_headers, admin_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=303)
    visitor_id = enrolled["visitor"]["id"]
    response = await client.request(
        "DELETE",
        f"/api/v1/visitors/{visitor_id}/biometric",
        headers=admin_headers,
        json={"reason": "Data subject deletion request"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["has_active_face_profile"] is False
    assert data["is_active"] is True

    fetched = await client.get(f"/api/v1/visitors/{visitor_id}", headers=admin_headers)
    assert fetched.status_code == 200

    identify = await client.post(
        "/api/v1/face/identify",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(303), "image/png")},
    )
    assert identify.json()["data"]["match_status"] == "UNKNOWN"


async def test_privacy_endpoints_require_permission(client, viewer_headers, kiosk_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=304)
    visitor_id = enrolled["visitor"]["id"]
    consents = await client.get(f"/api/v1/visitors/{visitor_id}/consents", headers=viewer_headers)
    assert consents.status_code == 403
    withdraw = await client.post(
        f"/api/v1/visitors/{visitor_id}/biometric/withdraw",
        headers=viewer_headers,
        json={"reason": "Nope"},
    )
    assert withdraw.status_code == 403
