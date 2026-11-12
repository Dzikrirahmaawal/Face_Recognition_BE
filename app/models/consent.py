from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID, EnumString, utcnow
from app.models.base import Base
from app.models.enums import ConsentStatus, ConsentType

if TYPE_CHECKING:
    from app.models.visitor import Visitor


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        Index("ix_consent_records_visitor_id", "visitor_id"),
        Index("ix_consent_records_type_status", "consent_type", "consent_status"),
        Index("ix_consent_records_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False
    )
    consent_type: Mapped[ConsentType] = mapped_column(EnumString(ConsentType, 40), nullable=False)
    policy_version: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    consent_status: Mapped[ConsentStatus] = mapped_column(EnumString(ConsentStatus, 20), nullable=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    visitor: Mapped["Visitor"] = relationship(back_populates="consent_records")
