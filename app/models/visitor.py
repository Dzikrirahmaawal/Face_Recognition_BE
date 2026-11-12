from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, LargeBinary, Unicode, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.attendance import AttendanceLog
    from app.models.consent import ConsentRecord
    from app.models.visit import Visit


class Visitor(TimestampMixin, Base):
    __tablename__ = "visitors"
    __table_args__ = (
        Index("ix_visitors_full_name", "full_name"),
        Index("ix_visitors_phone_number", "phone_number"),
        Index("ix_visitors_email", "email"),
        Index("ix_visitors_is_active", "is_active"),
        Index(
            "uq_visitors_identity_number_not_null",
            "identity_number",
            unique=True,
            mssql_where=text("identity_number IS NOT NULL"),
            sqlite_where=text("identity_number IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    visitor_code: Mapped[str] = mapped_column(Unicode(30), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Unicode(150), nullable=False)
    identity_number: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    company_name: Mapped[str | None] = mapped_column(Unicode(150), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(Unicode(30), nullable=True)
    email: Mapped[str | None] = mapped_column(Unicode(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    face_profiles: Mapped[list["FaceProfile"]] = relationship(
        back_populates="visitor", cascade="all, delete-orphan", lazy="selectin"
    )
    visits: Mapped[list["Visit"]] = relationship(back_populates="visitor", lazy="noload")
    consent_records: Mapped[list["ConsentRecord"]] = relationship(
        back_populates="visitor", cascade="all, delete-orphan", lazy="selectin"
    )
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(back_populates="visitor", lazy="noload")

    @property
    def has_active_face_profile(self) -> bool:
        return any(profile.is_active for profile in (self.face_profiles or []))


class FaceProfile(Base):
    __tablename__ = "face_profiles"
    __table_args__ = (
        Index("ix_face_profiles_visitor_id", "visitor_id"),
        Index("ix_face_profiles_is_active", "is_active"),
        Index(
            "uq_face_profiles_active_key",
            "active_profile_key",
            unique=True,
            mssql_where=text("active_profile_key IS NOT NULL"),
            sqlite_where=text("active_profile_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False
    )
    # AES-GCM encrypted embedding. Never exposed through APIs or logs.
    embedding_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    model_version: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    embedding_version: Mapped[str] = mapped_column(Unicode(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Equals visitor_id while active, NULL otherwise. Unique constraint prevents
    # multiple active profiles per visitor at the database level.
    active_profile_key: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_reason: Mapped[str | None] = mapped_column(Unicode(255), nullable=True)

    visitor: Mapped["Visitor"] = relationship(back_populates="face_profiles")
