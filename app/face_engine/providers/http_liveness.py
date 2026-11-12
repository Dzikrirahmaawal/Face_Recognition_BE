from __future__ import annotations

import cv2
import httpx
import numpy as np

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.face_engine.interfaces import LivenessProvider, LivenessResult


class HttpLivenessProvider(LivenessProvider):
    """Adapter for an external, commercially licensed liveness service.

    Contract: POST multipart/form-data with field `image` (JPEG) to
    FACE_LIVENESS_URL. Optional Bearer API key. Response JSON:
    {"passed": bool, "score": number|null, "reason": string|null}
    """

    name = "http"

    def __init__(self) -> None:
        self.url = settings.FACE_LIVENESS_URL
        self.api_key = settings.FACE_LIVENESS_API_KEY
        self.timeout = settings.FACE_LIVENESS_TIMEOUT_SECONDS

    def verify_liveness(self, image: np.ndarray) -> LivenessResult:
        ok, buffer = cv2.imencode(".jpg", image)
        if not ok:
            raise ProviderUnavailableError("Could not encode image for liveness verification")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.url,
                    headers=headers,
                    files={"image": ("capture.jpg", buffer.tobytes(), "image/jpeg")},
                )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise ProviderUnavailableError("Liveness provider request failed") from exc
        if not isinstance(payload, dict) or "passed" not in payload:
            raise ProviderUnavailableError("Liveness provider returned an invalid response")
        return LivenessResult(
            passed=bool(payload["passed"]),
            provider=self.name,
            score=float(payload["score"]) if payload.get("score") is not None else None,
            reason=payload.get("reason"),
        )

    def is_available(self) -> bool:
        return bool(self.url)
