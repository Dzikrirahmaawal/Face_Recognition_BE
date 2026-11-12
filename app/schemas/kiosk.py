from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class KioskCreate(BaseModel):
    kiosk_code: str = Field(min_length=1, max_length=30)
    device_name: str = Field(min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=150)


class KioskStatusUpdate(BaseModel):
    is_active: bool


class KioskOut(ORMModel):
    id: uuid.UUID
    kiosk_code: str
    device_name: str
    location: str | None = None
    is_active: bool
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KioskCreated(KioskOut):
    device_token: str = Field(description="Returned only once at creation. Store it securely in the kiosk.")
