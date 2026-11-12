from __future__ import annotations

import numpy as np
import pytest

from app.core.exceptions import ValidationAppError
from app.face_engine.detection import validate_single_face
from app.face_engine.providers.mock import MockFaceRecognitionProvider, MockLivenessProvider
from app.utils.images import decode_image
from tests.helpers import make_black_image, make_face_image, make_multi_face_image


def _as_array(raw: bytes) -> np.ndarray:
    return decode_image(raw, "image/png")


def test_mock_provider_detects_one_face_and_quality():
    provider = MockFaceRecognitionProvider()
    image = _as_array(make_face_image(1))
    faces = provider.detect_faces(image)
    assert len(faces) == 1
    quality = provider.validate_face_quality(image, faces[0])
    assert quality.acceptable is True
    assert quality.face_width >= 80


def test_mock_provider_detects_no_face_and_multiple_faces():
    provider = MockFaceRecognitionProvider()
    assert provider.detect_faces(_as_array(make_black_image())) == []
    assert len(provider.detect_faces(_as_array(make_multi_face_image()))) == 2


def test_embedding_is_deterministic_and_discriminative():
    provider = MockFaceRecognitionProvider()
    image_a = _as_array(make_face_image(5))
    image_a_again = _as_array(make_face_image(5))
    image_b = _as_array(make_face_image(6))
    face = provider.detect_faces(image_a)[0]

    emb_a = provider.generate_embedding(image_a, face)
    emb_a_again = provider.generate_embedding(image_a_again, face)
    emb_b = provider.generate_embedding(image_b, provider.detect_faces(image_b)[0])

    assert np.allclose(emb_a, emb_a_again)
    assert provider.compare_embeddings(emb_a, emb_a_again) == pytest.approx(1.0, abs=1e-6)
    assert provider.compare_embeddings(emb_a, emb_b) < 0.6


def test_validate_single_face_errors():
    with pytest.raises(ValidationAppError) as no_face:
        validate_single_face([])
    assert no_face.value.error_code == "NO_FACE_DETECTED"

    provider = MockFaceRecognitionProvider()
    faces = provider.detect_faces(_as_array(make_multi_face_image()))
    with pytest.raises(ValidationAppError) as multiple:
        validate_single_face(faces)
    assert multiple.value.error_code == "MULTIPLE_FACES_DETECTED"


def test_mock_liveness_passes():
    result = MockLivenessProvider().verify_liveness(_as_array(make_face_image(3)))
    assert result.passed is True
    assert result.score == 1.0


def test_image_validation_rejects_bad_input():
    with pytest.raises(ValidationAppError) as exc:
        decode_image(b"", "image/png")
    assert exc.value.error_code == "EMPTY_IMAGE"

    with pytest.raises(ValidationAppError) as exc:
        decode_image(b"not an image", "image/png")
    assert exc.value.error_code == "INVALID_IMAGE_FORMAT"

    with pytest.raises(ValidationAppError) as exc:
        decode_image(make_face_image(1), "image/jpeg")
    assert exc.value.error_code == "IMAGE_TYPE_MISMATCH"
