from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, TypeDecorator, Unicode
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER


class GUID(TypeDecorator):
    """Portable UUID type.

    SQL Server uses UNIQUEIDENTIFIER; SQLite (tests only) uses CHAR(36).
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):  # noqa: ANN001
        if dialect.name == "mssql":
            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect):  # noqa: ANN001
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect):  # noqa: ANN001
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class EnumString(TypeDecorator):
    """Stores enums as NVARCHAR on SQL Server and VARCHAR on SQLite."""

    impl = Unicode
    cache_ok = True

    def __init__(self, enum_cls: type[enum.Enum], length: int = 30):
        self.enum_cls = enum_cls
        super().__init__(length=length)

    def load_dialect_impl(self, dialect):  # noqa: ANN001
        return dialect.type_descriptor(Unicode(self.length))

    def process_bind_param(self, value: Any, dialect):  # noqa: ANN001
        if value is None:
            return None
        if isinstance(value, enum.Enum):
            return value.value
        return str(value)

    def process_result_value(self, value: Any, dialect):  # noqa: ANN001
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value
        return self.enum_cls(value)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
