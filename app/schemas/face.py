from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import MatchStatus
from app.schemas.visitor import VisitorSummary


class FaceEnrollResult(BaseModel):
    visitor: VisitorSummary
    profile_id: uuid.UUID
    model_version: str
    embedding_version: str
    consent_recorded: bool
    duplicate_review: bool = False


class FaceIdentifyResult(BaseModel):
    match_status: MatchStatus
    visitor: VisitorSummary | None = None
    confidence: Decimal | None = None
    review_required: bool = False
    active_visit_id: uuid.UUID | None = None
    active_visit_status: str | None = None


class FaceVerifyResult(BaseModel):
    matched: bool
    confidence: Decimal
    visitor_id: uuid.UUID


class LivenessResultSchema(BaseModel):
    passed: bool
    score: Decimal | None = None
    provider: str


class FaceEnrollFormMeta(BaseModel):
    """Documentation-only schema for multipart enrollment fields."""

    visitor_id: uuid.UUID | None = None
    full_name: str | None = Field(default=None, max_length=150)
    identity_number: str | None = Field(default=None, max_length=64)
    company_name: str | None = Field(default=None, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)
    email: str | None = None
    consent_granted: bool = True
    consent_policy_version: str = "1.0"
