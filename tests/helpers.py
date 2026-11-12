from __future__ import annotations

import cv2
import httpx
import numpy as np


def make_face_image(seed: int = 1, size: int = 240) -> bytes:
    rng = np.random.default_rng(seed)
    image = rng.integers(0, 256, (size, size, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def make_multi_face_image(size: int = 240) -> bytes:
    rng = np.random.default_rng(99)
    image = rng.integers(0, 256, (size, size, 3), dtype=np.uint8)
    image[0:5, 0:5] = (0, 0, 255)
    image[-5:, -5:] = (255, 0, 0)
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def make_black_image(size: int = 240) -> bytes:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


async def enroll_visitor(
    client: httpx.AsyncClient,
    kiosk_headers: dict,
    *,
    full_name: str = "Test Visitor",
    seed: int = 1,
    image: bytes | None = None,
) -> dict:
    response = await client.post(
        "/api/v1/face/enroll",
        headers=kiosk_headers,
        files={"image": ("face.png", image or make_face_image(seed), "image/png")},
        data={
            "full_name": full_name,
            "company_name": "Test Company",
            "phone_number": "08123456789",
            "consent_granted": "true",
            "consent_policy_version": "1.0",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]
