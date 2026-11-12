from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, Unicode, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID, EnumString, utcnow
from app.models.base import Base
from app.models.enums import AttendanceEventType

if TYPE_CHECKING:
    from app.models.kiosk import Kiosk
    from app.models.visit import Visit
    from app.models.visitor import Visitor


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    __table_args__ = (
        Index("ix_attendance_logs_visit_id", "visit_id"),
        Index("ix_attendance_logs_visitor_id", "visitor_id"),
        Index("ix_attendance_logs_event_timestamp", "event_timestamp"),
        Index("ix_attendance_logs_kiosk_id", "kiosk_id"),
        # For original events this is "{visit_id}:{event_type}". NULL for
        # corrections. Unique index enforces exactly one original CHECK_IN and
        # one original CHECK_OUT per visit (NULLs are not compared by SQL Server
        # or SQLite unique indexes).
        Index(
            "uq_attendance_logs_event_key",
            "event_unique_key",
            unique=True,
            mssql_where=text("event_unique_key IS NOT NULL"),
            sqlite_where=text("event_unique_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    visit_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("visits.id", ondelete="NO ACTION"), nullable=False
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("visitors.id", ondelete="NO ACTION"), nullable=False
    )
    event_type: Mapped[AttendanceEventType] = mapped_column(
        EnumString(AttendanceEventType, 20), nullable=False
    )
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    kiosk_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("kiosks.id", ondelete="SET NULL"), nullable=True
    )
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    is_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correction_of_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("attendance_logs.id", ondelete="NO ACTION"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(Unicode(255), nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_unique_key: Mapped[str | None] = mapped_column(Unicode(80), nullable=True)

    visit: Mapped["Visit"] = relationship(back_populates="attendance_logs", lazy="joined")
    visitor: Mapped["Visitor"] = relationship(back_populates="attendance_logs", lazy="joined")
    kiosk: Mapped["Kiosk | None"] = relationship(lazy="joined")
    correction_of: Mapped["AttendanceLog | None"] = relationship(remote_side="AttendanceLog.id", lazy="noload")
