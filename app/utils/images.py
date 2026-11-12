from __future__ import annotations

import cv2
import numpy as np

from app.core.config import settings
from app.core.exceptions import PayloadTooLargeError, ValidationAppError


def _sniff_image_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def decode_image(raw: bytes, declared_content_type: str | None = None) -> np.ndarray:
    if not raw:
        raise ValidationAppError("Empty image upload", error_code="EMPTY_IMAGE")
    if len(raw) > settings.MAX_UPLOAD_SIZE:
        raise PayloadTooLargeError(
            f"Image exceeds the maximum size of {settings.MAX_UPLOAD_SIZE} bytes"
        )
    sniffed = _sniff_image_type(raw)
    declared = (declared_content_type or "").lower().split(";")[0].strip()
    if sniffed is None:
        raise ValidationAppError(
            "Unsupported or invalid image format. Allowed: JPEG, PNG, WEBP.",
            error_code="INVALID_IMAGE_FORMAT",
        )
    if sniffed not in settings.allowed_image_types:
        raise ValidationAppError(
            f"Image type {sniffed} is not allowed",
            error_code="INVALID_IMAGE_FORMAT",
        )
    if declared and declared not in settings.allowed_image_types:
        raise ValidationAppError(
            f"Declared content type {declared} is not allowed",
            error_code="INVALID_IMAGE_FORMAT",
        )
    if declared and declared != sniffed:
        raise ValidationAppError(
            "Declared content type does not match the image contents",
            error_code="IMAGE_TYPE_MISMATCH",
        )
    array = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ValidationAppError("Image could not be decoded", error_code="INVALID_IMAGE")
    height, width = image.shape[:2]
    if width * height > settings.FACE_MAX_IMAGE_PIXELS:
        raise ValidationAppError("Image dimensions are too large", error_code="IMAGE_DIMENSIONS_TOO_LARGE")
    if width < 40 or height < 40:
        raise ValidationAppError("Image is too small", error_code="IMAGE_TOO_SMALL")
    return image
