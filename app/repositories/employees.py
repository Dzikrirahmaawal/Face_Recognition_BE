from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.employee import Employee


def get(db: Session, employee_id: uuid.UUID, for_update: bool = False) -> Employee | None:
    stmt = select(Employee).where(Employee.id == employee_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def get_by_code(db: Session, code: str) -> Employee | None:
    return db.scalars(select(Employee).where(Employee.employee_code == code)).first()


def get_by_email(db: Session, email: str) -> Employee | None:
    return db.scalars(select(Employee).where(Employee.email == email)).first()


def list_employees(
    db: Session,
    page: int,
    page_size: int,
    search: str | None = None,
    is_active: bool | None = None,
):
    stmt = select(Employee).order_by(Employee.full_name.asc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(like),
                Employee.employee_code.ilike(like),
                Employee.department.ilike(like),
                Employee.email.ilike(like),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Employee.is_active.is_(is_active))
    return stmt


def add(db: Session, employee: Employee) -> Employee:
    db.add(employee)
    return employee
