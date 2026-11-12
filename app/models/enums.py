from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    SECURITY = "SECURITY"
    VIEWER = "VIEWER"


class VisitStatus(str, enum.Enum):
    WAITING = "WAITING"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"


class AttendanceEventType(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class ConsentType(str, enum.Enum):
    BIOMETRIC_PROCESSING = "BIOMETRIC_PROCESSING"
    PRIVACY_NOTICE = "PRIVACY_NOTICE"


class ConsentStatus(str, enum.Enum):
    GRANTED = "GRANTED"
    WITHDRAWN = "WITHDRAWN"


class MatchStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class AttendanceMethod(str, enum.Enum):
    FACE = "FACE"
    MANUAL = "MANUAL"
