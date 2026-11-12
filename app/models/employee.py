from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, Unicode, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.visit import Visit


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index("ix_employees_full_name", "full_name"),
        Index("ix_employees_department", "department"),
        Index("ix_employees_is_active", "is_active"),
        Index(
            "uq_employees_email_not_null",
            "email",
            unique=True,
            mssql_where=text("email IS NOT NULL"),
            sqlite_where=text("email IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    employee_code: Mapped[str] = mapped_column(Unicode(30), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Unicode(150), nullable=False)
    department: Mapped[str | None] = mapped_column(Unicode(100), nullable=True)
    email: Mapped[str | None] = mapped_column(Unicode(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(Unicode(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    hosted_visits: Mapped[list["Visit"]] = relationship(back_populates="host_employee", lazy="noload")
