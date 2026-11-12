from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]
    score: float = 1.0


@dataclass
class QualityReport:
    acceptable: bool
    issues: list[str] = field(default_factory=list)
    face_width: int = 0
    face_height: int = 0
    blur_score: float = 0.0
    brightness: float = 0.0


@dataclass(frozen=True)
class LivenessResult:
    passed: bool
    provider: str
    score: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class RecognitionCandidate:
    profile_id: uuid.UUID
    visitor_id: uuid.UUID
    similarity: float


@dataclass(frozen=True)
class IdentificationOutcome:
    status: str
    best: RecognitionCandidate | None
    second: RecognitionCandidate | None
    ambiguous: bool


@dataclass(frozen=True)
class EnrolledProfile:
    profile_id: uuid.UUID
    visitor_id: uuid.UUID
    embedding: np.ndarray


class FaceRecognitionProvider(ABC):
    name: str
    model_version: str
    embedding_version: str

    @abstractmethod
    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        ...

    @abstractmethod
    def validate_face_quality(self, image: np.ndarray, face: DetectedFace) -> QualityReport:
        ...

    @abstractmethod
    def generate_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        ...

    @abstractmethod
    def compare_embeddings(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        ...

    def identify_face(
        self,
        embedding: np.ndarray,
        profiles: list[EnrolledProfile],
        *,
        match_threshold: float,
        review_threshold: float,
        ambiguity_margin: float,
    ) -> IdentificationOutcome:
        candidates: list[RecognitionCandidate] = []
        for profile in profiles:
            similarity = self.compare_embeddings(embedding, profile.embedding)
            candidates.append(
                RecognitionCandidate(
                    profile_id=profile.profile_id,
                    visitor_id=profile.visitor_id,
                    similarity=float(similarity),
                )
            )
        candidates.sort(key=lambda item: item.similarity, reverse=True)
        if not candidates:
            return IdentificationOutcome("UNKNOWN", None, None, False)
        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        ambiguous = bool(
            second is not None
            and best.similarity >= match_threshold
            and second.similarity >= match_threshold
            and (best.similarity - second.similarity) < ambiguity_margin
        )
        if ambiguous:
            return IdentificationOutcome("REVIEW_REQUIRED", best, second, True)
        if best.similarity >= match_threshold:
            return IdentificationOutcome("MATCHED", best, second, False)
        if best.similarity >= review_threshold:
            return IdentificationOutcome("REVIEW_REQUIRED", best, second, False)
        return IdentificationOutcome("UNKNOWN", None, None, False)

    def is_available(self) -> bool:
        return True


class LivenessProvider(ABC):
    name: str

    @abstractmethod
    def verify_liveness(self, image: np.ndarray) -> LivenessResult:
        ...

    def is_available(self) -> bool:
        return True
