from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.employee import Employee
from app.models.user import User
from app.repositories import employees as employees_repo
from app.repositories.base import paginate
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services import audit_service


def get_or_404(db: Session, employee_id: uuid.UUID, for_update: bool = False) -> Employee:
    employee = employees_repo.get(db, employee_id, for_update=for_update)
    if employee is None:
        raise NotFoundError("Employee not found", error_code="EMPLOYEE_NOT_FOUND")
    return employee


def create_employee(
    db: Session, *, data: EmployeeCreate, actor: User, ip_address: str | None
) -> Employee:
    if employees_repo.get_by_code(db, data.employee_code):
        raise ConflictError("Employee code is already in use", error_code="EMPLOYEE_CODE_EXISTS")
    email = str(data.email).lower() if data.email else None
    if email and employees_repo.get_by_email(db, email):
        raise ConflictError("Employee email is already in use", error_code="EMPLOYEE_EMAIL_EXISTS")
    employee = Employee(
        employee_code=data.employee_code,
        full_name=data.full_name,
        department=data.department,
        email=email,
        phone_number=data.phone_number,
        is_active=True,
    )
    employees_repo.add(db, employee)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Employee violates a unique constraint", error_code="EMPLOYEE_CONFLICT") from exc
    audit_service.record(
        db,
        action="EMPLOYEE_CREATED",
        entity_type="employee",
        entity_id=employee.id,
        description=f"Employee {employee.employee_code} created",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(employee)
    return employee


def list_employees(
    db: Session, *, page: int, page_size: int, search: str | None, is_active: bool | None
):
    stmt = employees_repo.list_employees(db, page, page_size, search=search, is_active=is_active)
    return paginate(db, stmt, page, page_size)


def update_employee(
    db: Session, *, employee_id: uuid.UUID, data: EmployeeUpdate, actor: User, ip_address: str | None
) -> Employee:
    employee = get_or_404(db, employee_id)
    changes = data.model_dump(exclude_unset=True)
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).lower()
        existing = employees_repo.get_by_email(db, changes["email"])
        if existing is not None and existing.id != employee.id:
            raise ConflictError("Employee email is already in use", error_code="EMPLOYEE_EMAIL_EXISTS")
    for field, value in changes.items():
        setattr(employee, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Employee update violates a unique constraint", error_code="EMPLOYEE_CONFLICT") from exc
    audit_service.record(
        db,
        action="EMPLOYEE_UPDATED",
        entity_type="employee",
        entity_id=employee.id,
        description=f"Fields updated: {', '.join(sorted(changes.keys()))}",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(employee)
    return employee


def deactivate_employee(
    db: Session, *, employee_id: uuid.UUID, actor: User, ip_address: str | None
) -> Employee:
    employee = get_or_404(db, employee_id, for_update=True)
    employee.is_active = False
    audit_service.record(
        db,
        action="EMPLOYEE_DEACTIVATED",
        entity_type="employee",
        entity_id=employee.id,
        description="Employee soft-deleted/deactivated",
        user_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(employee)
    return employee
