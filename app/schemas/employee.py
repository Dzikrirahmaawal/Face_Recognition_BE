from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=30)
    full_name: str = Field(min_length=1, max_length=150)
    department: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=30)


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    department: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None


class EmployeeOut(ORMModel):
    id: uuid.UUID
    employee_code: str
    full_name: str
    department: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
