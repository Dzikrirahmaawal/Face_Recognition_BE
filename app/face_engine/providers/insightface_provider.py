"""ArcFace-compatible provider backed by InsightFace.

LICENSING: InsightFace code and the pretrained `buffalo_l` model have their own
license terms. Public availability does not imply commercial permission. The
deploying organization must verify commercial licensing (and model provenance)
before enabling this provider in production.

This adapter is optional: install `insightface` and `onnxruntime` separately and
set FACE_RECOGNITION_PROVIDER=insightface and FACE_MODEL_PATH.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.face_engine.detection import assess_quality
from app.face_engine.interfaces import DetectedFace, FaceRecognitionProvider, QualityReport


class InsightFaceProvider(FaceRecognitionProvider):
    name = "insightface"
    model_version = settings.FACE_MODEL_VERSION
    embedding_version = settings.FACE_EMBEDDING_VERSION

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._app = None

    def _ensure_loaded(self):
        if self._app is not None:
            return self._app
        try:
            from insightface.app import FaceAnalysis  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise ProviderUnavailableError(
                "insightface is not installed. Install insightface and onnxruntime, or use another provider."
            ) from exc
        try:
            app = FaceAnalysis(name="buffalo_l", root=settings.FACE_MODEL_PATH, providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=-1, det_size=(640, 640))
        except Exception as exc:  # pragma: no cover - depends on model files
            raise ProviderUnavailableError("Unable to load the InsightFace model") from exc
        self._app = app
        return app

    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        app = self._ensure_loaded()
        with self._lock:
            faces = app.get(image)
        results: list[DetectedFace] = []
        for face in faces:
            x1, y1, x2, y2 = [int(v) for v in face.bbox]
            results.append(
                DetectedFace(bbox=(x1, y1, max(1, x2 - x1), max(1, y2 - y1)), score=float(face.det_score))
            )
        return results

    def validate_face_quality(self, image: np.ndarray, face: DetectedFace) -> QualityReport:
        return assess_quality(image, face)

    def generate_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        app = self._ensure_loaded()
        with self._lock:
            faces = app.get(image)
        if not faces:
            raise ProviderUnavailableError("Face disappeared during embedding generation")
        target = max(faces, key=lambda item: float(item.det_score))
        embedding = np.asarray(target.embedding, dtype=np.float32)
        norm = float(np.linalg.norm(embedding))
        return embedding / norm if norm else embedding

    def compare_embeddings(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        if embedding_a.shape != embedding_b.shape:
            return 0.0
        a = embedding_a.astype(np.float64)
        b = embedding_b.astype(np.float64)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))

    def is_available(self) -> bool:
        try:
            self._ensure_loaded()
            return True
        except Exception:
            return False
