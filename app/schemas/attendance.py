from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import AttendanceEventType, AttendanceMethod
from app.schemas.common import ORMModel


class CheckInRequest(BaseModel):
    visitor_id: uuid.UUID
    kiosk_id: uuid.UUID | None = None
    visit_id: uuid.UUID | None = None
    purpose: str | None = Field(default=None, max_length=255)
    host_employee_id: uuid.UUID | None = None
    method: AttendanceMethod = AttendanceMethod.MANUAL
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1)


class CheckOutRequest(BaseModel):
    visitor_id: uuid.UUID
    kiosk_id: uuid.UUID | None = None
    visit_id: uuid.UUID | None = None
    method: AttendanceMethod = AttendanceMethod.MANUAL
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1)


class AttendanceLogOut(ORMModel):
    id: uuid.UUID
    visit_id: uuid.UUID
    visitor_id: uuid.UUID
    event_type: AttendanceEventType
    event_timestamp: datetime
    kiosk_id: uuid.UUID | None = None
    confidence_score: Decimal | None = None
    is_correction: bool = False
    correction_of_id: uuid.UUID | None = None
    correction_reason: str | None = None
    created_at: datetime


class AttendanceCorrectionRequest(BaseModel):
    corrected_event_type: AttendanceEventType
    corrected_timestamp: datetime
    reason: str = Field(min_length=3, max_length=255)
