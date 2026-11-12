from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.attendance import AttendanceLog


class Kiosk(TimestampMixin, Base):
    __tablename__ = "kiosks"
    __table_args__ = (
        Index("ix_kiosks_is_active", "is_active"),
        Index("ix_kiosks_last_seen_at", "last_seen_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    kiosk_code: Mapped[str] = mapped_column(Unicode(30), unique=True, nullable=False)
    device_name: Mapped[str] = mapped_column(Unicode(150), nullable=False)
    device_token_hash: Mapped[str] = mapped_column(Unicode(64), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(Unicode(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(back_populates="kiosk", lazy="noload")
