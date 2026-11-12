"""Development/test-only face provider.

This provider is NOT real facial recognition. It performs deterministic image
hashing so that integration tests and the local camera client can exercise the
full workflow. It must never be enabled in production (enforced by config).
"""

from __future__ import annotations

import hashlib

import cv2
import numpy as np

from app.face_engine.detection import assess_quality
from app.face_engine.interfaces import (
    DetectedFace,
    FaceRecognitionProvider,
    LivenessProvider,
    LivenessResult,
    QualityReport,
)


class MockFaceRecognitionProvider(FaceRecognitionProvider):
    name = "mock"
    model_version = "mock-v1"
    embedding_version = "mock-embedding-v1"

    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        if image is None or image.size == 0:
            return []
        height, width = image.shape[:2]
        if min(height, width) < 40 or float(image.mean()) < 5.0:
            return []
        # Test hook: a red patch top-left and a blue patch bottom-right means
        # "two faces", allowing the API's multi-face validation to be tested.
        tl = image[0:5, 0:5].mean(axis=(0, 1))
        br = image[-5:, -5:].mean(axis=(0, 1))
        if tl[2] > 180 and tl[1] < 80 and br[0] > 180 and br[1] < 80:
            return [
                DetectedFace(bbox=(10, 10, width // 3, height // 3)),
                DetectedFace(bbox=(width // 2, height // 2, width // 3, height // 3)),
            ]
        box_w = max(60, int(width * 0.6))
        box_h = max(60, int(height * 0.6))
        x = max(0, (width - box_w) // 2)
        y = max(0, (height - box_h) // 2)
        return [DetectedFace(bbox=(x, y, box_w, box_h), score=0.99)]

    def validate_face_quality(self, image: np.ndarray, face: DetectedFace) -> QualityReport:
        return assess_quality(image, face)

    def generate_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        x, y, w, h = face.bbox
        crop = image[max(0, y) : y + h, max(0, x) : x + w]
        if crop.size == 0:
            crop = image
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        pixel_vector = resized.flatten() - 0.5
        digest = hashlib.sha256(image.tobytes()).digest()
        hash_vector = (np.frombuffer(digest, dtype=np.uint8).astype(np.float32) - 127.5) / 127.5
        vector = np.concatenate([pixel_vector, hash_vector])
        norm = float(np.linalg.norm(vector))
        return vector / norm if norm else vector

    def compare_embeddings(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        if embedding_a.shape != embedding_b.shape:
            return 0.0
        a = embedding_a.astype(np.float64)
        b = embedding_b.astype(np.float64)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))


class MockLivenessProvider(LivenessProvider):
    """Development/test-only liveness provider. Always passes."""

    name = "mock"

    def verify_liveness(self, image: np.ndarray) -> LivenessResult:
        return LivenessResult(passed=True, provider=self.name, score=1.0)
