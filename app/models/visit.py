from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Unicode, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID, EnumString
from app.models.base import Base, TimestampMixin
from app.models.enums import VisitStatus

if TYPE_CHECKING:
    from app.models.attendance import AttendanceLog
    from app.models.employee import Employee
    from app.models.visitor import Visitor


class Visit(TimestampMixin, Base):
    __tablename__ = "visits"
    __table_args__ = (
        CheckConstraint(
            "(visit_status IN ('WAITING','CHECKED_IN') AND active_visit_key = visitor_id) "
            "OR (visit_status IN ('CHECKED_OUT','CANCELLED') AND active_visit_key IS NULL)",
            name="active_key_matches_status",
        ),
        Index("ix_visits_visitor_id", "visitor_id"),
        Index("ix_visits_host_employee_id", "host_employee_id"),
        Index("ix_visits_visit_status", "visit_status"),
        Index("ix_visits_check_in_at", "check_in_at"),
        Index(
            "uq_visits_active_key",
            "active_visit_key",
            unique=True,
            mssql_where=text("active_visit_key IS NOT NULL"),
            sqlite_where=text("active_visit_key IS NOT NULL"),
        ),
        # SQL Server filtered unique indexes: a visitor may have at most one
        # WAITING visit and at most one CHECKED_IN visit. The active_visit_key
        # unique index is the portable, definitive guard across both states.
        Index(
            "uq_visits_one_waiting_per_visitor",
            "visitor_id",
            unique=True,
            mssql_where=text("visit_status = 'WAITING'"),
            sqlite_where=text("1 = 0"),
        ),
        Index(
            "uq_visits_one_checked_in_per_visitor",
            "visitor_id",
            unique=True,
            mssql_where=text("visit_status = 'CHECKED_IN'"),
            sqlite_where=text("1 = 0"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("visitors.id", ondelete="NO ACTION"), nullable=False
    )
    purpose: Mapped[str | None] = mapped_column(Unicode(255), nullable=True)
    host_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    visit_status: Mapped[VisitStatus] = mapped_column(
        EnumString(VisitStatus, 20), nullable=False, default=VisitStatus.WAITING
    )
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_visit_key: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    visitor: Mapped["Visitor"] = relationship(back_populates="visits", lazy="joined")
    host_employee: Mapped["Employee | None"] = relationship(back_populates="hosted_visits", lazy="joined")
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        back_populates="visit", lazy="selectin", order_by="AttendanceLog.event_timestamp"
    )
