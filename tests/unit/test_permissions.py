from __future__ import annotations

import pytest

from app.core.permissions import ALL_PERMISSIONS, Permission, role_has_permission
from app.models.enums import UserRole


def test_super_admin_has_every_permission():
    for permission in Permission:
        assert role_has_permission(UserRole.SUPER_ADMIN, permission)


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        (UserRole.ADMIN, Permission.USER_MANAGE, False),
        (UserRole.ADMIN, Permission.VISITOR_WRITE, True),
        (UserRole.ADMIN, Permission.KIOSK_MANAGE, False),
        (UserRole.RECEPTIONIST, Permission.FACE_ENROLL, True),
        (UserRole.RECEPTIONIST, Permission.VISITOR_DELETE, False),
        (UserRole.RECEPTIONIST, Permission.REPORT_READ, False),
        (UserRole.SECURITY, Permission.ATTENDANCE_WRITE, True),
        (UserRole.SECURITY, Permission.VISITOR_WRITE, False),
        (UserRole.VIEWER, Permission.REPORT_READ, True),
        (UserRole.VIEWER, Permission.ATTENDANCE_WRITE, False),
    ],
)
def test_role_permission_matrix(role, permission, expected):
    assert role_has_permission(role, permission) is expected


def test_all_permissions_matches_enum():
    assert ALL_PERMISSIONS == frozenset(Permission)
