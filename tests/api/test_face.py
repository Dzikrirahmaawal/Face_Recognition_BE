from __future__ import annotations

from tests.helpers import (
    enroll_visitor,
    make_black_image,
    make_face_image,
    make_multi_face_image,
)


async def test_enroll_identify_and_verify(client, kiosk_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, full_name="Budi Santoso", seed=7)
    assert enrolled["visitor"]["full_name"] == "Budi Santoso"
    assert "embedding_data" not in str(enrolled).lower()

    identified = await client.post(
        "/api/v1/face/identify",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(7), "image/png")},
    )
    assert identified.status_code == 200, identified.text
    data = identified.json()["data"]
    assert data["match_status"] == "MATCHED"
    assert data["visitor"]["id"] == enrolled["visitor"]["id"]
    assert "embedding_data" not in str(data).lower()

    verified = await client.post(
        "/api/v1/face/verify",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(7), "image/png")},
        data={"visitor_id": enrolled["visitor"]["id"]},
    )
    assert verified.status_code == 200
    assert verified.json()["data"]["matched"] is True


async def test_identify_unknown_face(client, kiosk_headers):
    await enroll_visitor(client, kiosk_headers, seed=10)
    response = await client.post(
        "/api/v1/face/identify",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(12345), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["match_status"] == "UNKNOWN"


async def test_duplicate_face_enrollment_rejected(client, kiosk_headers):
    first = await enroll_visitor(client, kiosk_headers, full_name="First Person", seed=42)
    second = await client.post(
        "/api/v1/face/enroll",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(42), "image/png")},
        data={
            "full_name": "Second Person",
            "consent_granted": "true",
            "consent_policy_version": "1.0",
        },
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "FACE_DUPLICATE_DETECTED"
    assert second.json()["details"]["review_required"] is True
    assert second.json()["details"]["matched_visitor_id"] == first["visitor"]["id"]


async def test_no_face_and_multiple_faces(client, kiosk_headers):
    no_face = await client.post(
        "/api/v1/face/enroll",
        headers=kiosk_headers,
        files={"image": ("face.png", make_black_image(), "image/png")},
        data={"full_name": "No Face", "consent_granted": "true", "consent_policy_version": "1.0"},
    )
    assert no_face.status_code == 422
    assert no_face.json()["error_code"] == "NO_FACE_DETECTED"

    multi = await client.post(
        "/api/v1/face/enroll",
        headers=kiosk_headers,
        files={"image": ("face.png", make_multi_face_image(), "image/png")},
        data={"full_name": "Two Faces", "consent_granted": "true", "consent_policy_version": "1.0"},
    )
    assert multi.status_code == 422
    assert multi.json()["error_code"] == "MULTIPLE_FACES_DETECTED"


async def test_enrollment_requires_consent(client, kiosk_headers):
    response = await client.post(
        "/api/v1/face/enroll",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(5), "image/png")},
        data={"full_name": "No Consent", "consent_granted": "false"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "CONSENT_REQUIRED"


async def test_invalid_image_format(client, kiosk_headers):
    response = await client.post(
        "/api/v1/face/enroll",
        headers=kiosk_headers,
        files={"image": ("face.txt", b"not-an-image", "text/plain")},
        data={"full_name": "Bad Image", "consent_granted": "true"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] in {"INVALID_IMAGE_FORMAT", "INVALID_IMAGE"}


async def test_liveness_endpoint(client, kiosk_headers):
    response = await client.post(
        "/api/v1/face/liveness",
        headers=kiosk_headers,
        files={"image": ("face.png", make_face_image(8), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["passed"] is True


async def test_delete_face_profile_removes_biometric_data(client, kiosk_headers, admin_headers, db):
    from app.models import FaceProfile

    enrolled = await enroll_visitor(client, kiosk_headers, seed=77)
    profile_id = enrolled["profile_id"]
    response = await client.delete(
        f"/api/v1/face/profiles/{profile_id}?delete_biometrics=true&reason=GDPR%20request",
        headers=admin_headers,
    )
    assert response.status_code == 200
    profile = db.get(FaceProfile, profile_id)
    assert profile is not None
    assert profile.embedding_data is None
    assert profile.is_active is False
    assert profile.deleted_at is not None


async def test_face_endpoints_require_kiosk_or_staff(client):
    response = await client.post(
        "/api/v1/face/identify",
        files={"image": ("face.png", make_face_image(1), "image/png")},
    )
    assert response.status_code == 401

    bad = await client.post(
        "/api/v1/face/identify",
        headers={"X-Kiosk-Token": "kiosk_invalid"},
        files={"image": ("face.png", make_face_image(1), "image/png")},
    )
    assert bad.status_code == 401
    assert bad.json()["error_code"] == "INVALID_KIOSK_TOKEN"
