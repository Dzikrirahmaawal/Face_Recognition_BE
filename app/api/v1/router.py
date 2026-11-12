from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    attendance,
    auth,
    employees,
    face,
    kiosks,
    reports,
    visitors,
    visits,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(visitors.router)
api_router.include_router(face.router)
api_router.include_router(attendance.router)
api_router.include_router(visits.router)
api_router.include_router(employees.router)
api_router.include_router(reports.router)
api_router.include_router(kiosks.router)
api_router.include_router(admin.router)
