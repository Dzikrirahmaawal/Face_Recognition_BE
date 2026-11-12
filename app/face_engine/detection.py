from __future__ import annotations

import cv2
import numpy as np

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.face_engine.interfaces import DetectedFace, QualityReport

_cascade: cv2.CascadeClassifier | None = None


def _get_cascade() -> cv2.CascadeClassifier | None:
    global _cascade
    if _cascade is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        classifier = cv2.CascadeClassifier(path)
        _cascade = classifier if not classifier.empty() else None
    return _cascade


def detect_faces_opencv(image: np.ndarray) -> list[DetectedFace]:
    classifier = _get_cascade()
    if classifier is None:
        return []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    return [DetectedFace(bbox=(int(x), int(y), int(w), int(h)), score=1.0) for (x, y, w, h) in faces]


def assess_quality(image: np.ndarray, face: DetectedFace) -> QualityReport:
    x, y, w, h = face.bbox
    x = max(0, x)
    y = max(0, y)
    w = max(1, min(w, image.shape[1] - x))
    h = max(1, min(h, image.shape[0] - y))
    crop = image[y : y + h, x : x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    issues: list[str] = []
    if min(w, h) < settings.FACE_MIN_FACE_SIZE:
        issues.append("FACE_TOO_SMALL")
    if blur < settings.FACE_MIN_BLUR_SCORE:
        issues.append("FACE_TOO_BLURRY")
    if brightness < settings.FACE_MIN_BRIGHTNESS:
        issues.append("FACE_TOO_DARK")
    if brightness > settings.FACE_MAX_BRIGHTNESS:
        issues.append("FACE_TOO_BRIGHT")
    return QualityReport(
        acceptable=not issues,
        issues=issues,
        face_width=w,
        face_height=h,
        blur_score=round(blur, 2),
        brightness=round(brightness, 2),
    )


def validate_single_face(faces: list[DetectedFace]) -> DetectedFace:
    if not faces:
        raise ValidationAppError("No face was detected in the image", error_code="NO_FACE_DETECTED")
    if len(faces) > 1:
        raise ValidationAppError(
            "Multiple faces were detected. Exactly one face is required.",
            error_code="MULTIPLE_FACES_DETECTED",
        )
    return faces[0]
