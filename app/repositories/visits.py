from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import VisitStatus
from app.models.visit import Visit


def get(db: Session, visit_id: uuid.UUID, for_update: bool = False) -> Visit | None:
    stmt = (
        select(Visit)
        .where(Visit.id == visit_id)
        .options(joinedload(Visit.visitor), joinedload(Visit.host_employee), selectinload(Visit.attendance_logs))
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def get_active_for_visitor(db: Session, visitor_id: uuid.UUID, for_update: bool = False) -> Visit | None:
    stmt = (
        select(Visit)
        .where(
            Visit.visitor_id == visitor_id,
            Visit.visit_status.in_([VisitStatus.WAITING, VisitStatus.CHECKED_IN]),
        )
        .options(joinedload(Visit.visitor), joinedload(Visit.host_employee), selectinload(Visit.attendance_logs))
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def list_visits(
    db: Session,
    page: int,
    page_size: int,
    visitor_id: uuid.UUID | None = None,
    status: VisitStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
):
    stmt = (
        select(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.host_employee))
        .order_by(Visit.created_at.desc())
    )
    if visitor_id:
        stmt = stmt.where(Visit.visitor_id == visitor_id)
    if status:
        stmt = stmt.where(Visit.visit_status == status)
    if date_from:
        stmt = stmt.where(Visit.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Visit.created_at <= date_to)
    if search:
        from app.models.visitor import Visitor

        stmt = stmt.join(Visitor, Visit.visitor_id == Visitor.id).where(
            or_(Visitor.full_name.ilike(f"%{search}%"), Visitor.visitor_code.ilike(f"%{search}%"))
        )
    return stmt


def add(db: Session, visit: Visit) -> Visit:
    db.add(visit)
    return visit
