from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import VisitStatus
from app.schemas.common import ORMModel
from app.schemas.visitor import VisitorSummary


class VisitCreate(BaseModel):
    visitor_id: uuid.UUID
    purpose: str | None = Field(default=None, max_length=255)
    host_employee_id: uuid.UUID | None = None


class VisitUpdate(BaseModel):
    purpose: str | None = Field(default=None, max_length=255)
    host_employee_id: uuid.UUID | None = None


class VisitCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class VisitOut(ORMModel):
    id: uuid.UUID
    visitor_id: uuid.UUID
    visitor: VisitorSummary | None = None
    purpose: str | None = None
    host_employee_id: uuid.UUID | None = None
    visit_status: VisitStatus
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
