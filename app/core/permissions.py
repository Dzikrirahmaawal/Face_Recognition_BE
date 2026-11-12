from __future__ import annotations

import enum

from app.models.enums import UserRole


class Permission(str, enum.Enum):
    USER_MANAGE = "user:manage"
    KIOSK_MANAGE = "kiosk:manage"
    KIOSK_READ = "kiosk:read"
    VISITOR_READ = "visitor:read"
    VISITOR_WRITE = "visitor:write"
    VISITOR_DELETE = "visitor:delete"
    FACE_ENROLL = "face:enroll"
    FACE_IDENTIFY = "face:identify"
    FACE_VERIFY = "face:verify"
    FACE_DELETE = "face:delete"
    ATTENDANCE_READ = "attendance:read"
    ATTENDANCE_WRITE = "attendance:write"
    ATTENDANCE_CORRECT = "attendance:correct"
    VISIT_READ = "visit:read"
    VISIT_WRITE = "visit:write"
    EMPLOYEE_READ = "employee:read"
    EMPLOYEE_WRITE = "employee:write"
    REPORT_READ = "report:read"
    AUDIT_READ = "audit:read"
    PRIVACY_MANAGE = "privacy:manage"


ALL_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.SUPER_ADMIN: ALL_PERMISSIONS,
    UserRole.ADMIN: frozenset(
        {
            Permission.VISITOR_READ,
            Permission.VISITOR_WRITE,
            Permission.VISITOR_DELETE,
            Permission.FACE_ENROLL,
            Permission.FACE_IDENTIFY,
            Permission.FACE_VERIFY,
            Permission.FACE_DELETE,
            Permission.ATTENDANCE_READ,
            Permission.ATTENDANCE_WRITE,
            Permission.ATTENDANCE_CORRECT,
            Permission.VISIT_READ,
            Permission.VISIT_WRITE,
            Permission.EMPLOYEE_READ,
            Permission.EMPLOYEE_WRITE,
            Permission.REPORT_READ,
            Permission.AUDIT_READ,
            Permission.KIOSK_READ,
            Permission.PRIVACY_MANAGE,
        }
    ),
    UserRole.RECEPTIONIST: frozenset(
        {
            Permission.VISITOR_READ,
            Permission.VISITOR_WRITE,
            Permission.FACE_ENROLL,
            Permission.FACE_IDENTIFY,
            Permission.FACE_VERIFY,
            Permission.ATTENDANCE_READ,
            Permission.ATTENDANCE_WRITE,
            Permission.VISIT_READ,
            Permission.VISIT_WRITE,
            Permission.EMPLOYEE_READ,
            Permission.KIOSK_READ,
        }
    ),
    UserRole.SECURITY: frozenset(
        {
            Permission.VISITOR_READ,
            Permission.FACE_IDENTIFY,
            Permission.FACE_VERIFY,
            Permission.ATTENDANCE_READ,
            Permission.ATTENDANCE_WRITE,
            Permission.VISIT_READ,
            Permission.KIOSK_READ,
        }
    ),
    UserRole.VIEWER: frozenset(
        {
            Permission.VISITOR_READ,
            Permission.ATTENDANCE_READ,
            Permission.VISIT_READ,
            Permission.REPORT_READ,
        }
    ),
}


def permissions_for_role(role: UserRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in permissions_for_role(role)
