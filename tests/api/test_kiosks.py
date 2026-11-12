from __future__ import annotations


async def test_kiosk_creation_returns_token_once(client, admin_headers):
    created = await client.post(
        "/api/v1/kiosks",
        headers=admin_headers,
        json={"kiosk_code": "K-100", "device_name": "Front Desk", "location": "Floor 1"},
    )
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["device_token"].startswith("kiosk_")

    listed = await client.get("/api/v1/kiosks", headers=admin_headers)
    assert listed.status_code == 200
    assert "device_token" not in listed.text
    assert "device_token_hash" not in listed.text


async def test_kiosk_status_toggle_and_auth(client, admin_headers, kiosk):
    token_headers = {"X-Kiosk-Token": kiosk["device_token"]}
    before = await client.post(
        "/api/v1/face/identify",
        headers=token_headers,
        files={"image": ("face.png", b"invalid", "image/png")},
    )
    assert before.status_code in {422, 400}

    disabled = await client.patch(
        f"/api/v1/kiosks/{kiosk['id']}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["is_active"] is False

    after = await client.post(
        "/api/v1/face/identify",
        headers=token_headers,
        files={"image": ("face.png", b"invalid", "image/png")},
    )
    assert after.status_code == 401
    assert after.json()["error_code"] == "KIOSK_DISABLED"


async def test_viewer_cannot_manage_kiosks(client, viewer_headers):
    response = await client.get("/api/v1/kiosks", headers=viewer_headers)
    assert response.status_code == 403
    create = await client.post(
        "/api/v1/kiosks",
        headers=viewer_headers,
        json={"kiosk_code": "K-200", "device_name": "Nope"},
    )
    assert create.status_code == 403
