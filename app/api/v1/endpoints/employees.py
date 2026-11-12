from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import require_permissions
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.common import pagination_meta, success_payload
from app.schemas.employee import EmployeeCreate, EmployeeOut, EmployeeUpdate
from app.services import employee_service

router = APIRouter(prefix="/employees", tags=["Employees"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", status_code=201)
def create_employee(
    payload: EmployeeCreate,
    request: Request,
    user: User = Depends(require_permissions(Permission.EMPLOYEE_WRITE)),
    db: Session = Depends(get_db),
):
    employee = employee_service.create_employee(db, data=payload, actor=user, ip_address=_ip(request))
    return success_payload(
        data=EmployeeOut.model_validate(employee).model_dump(mode="json"),
        message="Employee created",
    )


@router.get("")
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = Query(None, max_length=150),
    is_active: bool | None = Query(None),
    _: User = Depends(require_permissions(Permission.EMPLOYEE_READ)),
    db: Session = Depends(get_db),
):
    items, total = employee_service.list_employees(
        db, page=page, page_size=page_size, search=search, is_active=is_active
    )
    return success_payload(
        data=[EmployeeOut.model_validate(item).model_dump(mode="json") for item in items],
        message="Employees retrieved",
        meta=pagination_meta(page, page_size, total),
    )


@router.get("/{employee_id}")
def get_employee(
    employee_id: uuid.UUID,
    _: User = Depends(require_permissions(Permission.EMPLOYEE_READ)),
    db: Session = Depends(get_db),
):
    employee = employee_service.get_or_404(db, employee_id)
    return success_payload(
        data=EmployeeOut.model_validate(employee).model_dump(mode="json"),
        message="Employee retrieved",
    )


@router.put("/{employee_id}")
def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    request: Request,
    user: User = Depends(require_permissions(Permission.EMPLOYEE_WRITE)),
    db: Session = Depends(get_db),
):
    employee = employee_service.update_employee(
        db, employee_id=employee_id, data=payload, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=EmployeeOut.model_validate(employee).model_dump(mode="json"),
        message="Employee updated",
    )


@router.delete("/{employee_id}")
def deactivate_employee(
    employee_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permissions(Permission.EMPLOYEE_WRITE)),
    db: Session = Depends(get_db),
):
    employee = employee_service.deactivate_employee(
        db, employee_id=employee_id, actor=user, ip_address=_ip(request)
    )
    return success_payload(
        data=EmployeeOut.model_validate(employee).model_dump(mode="json"),
        message="Employee deactivated",
    )
