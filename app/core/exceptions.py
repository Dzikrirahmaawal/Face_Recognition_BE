from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        self.headers = headers or {}


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required", error_code: str = "UNAUTHORIZED") -> None:
        super().__init__(message, status_code=401, error_code=error_code, headers={"WWW-Authenticate": "Bearer"})


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action") -> None:
        super().__init__(message, status_code=403, error_code="FORBIDDEN")


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", error_code: str = "NOT_FOUND") -> None:
        super().__init__(message, status_code=404, error_code=error_code)


class ConflictError(AppError):
    def __init__(self, message: str, error_code: str = "CONFLICT", details: Any = None) -> None:
        super().__init__(message, status_code=409, error_code=error_code, details=details)


class ValidationAppError(AppError):
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", details: Any = None) -> None:
        super().__init__(message, status_code=422, error_code=error_code, details=details)


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many requests") -> None:
        super().__init__(message, status_code=429, error_code="RATE_LIMITED")


class ProviderUnavailableError(AppError):
    def __init__(self, message: str = "Face recognition provider is unavailable") -> None:
        super().__init__(message, status_code=503, error_code="FACE_PROVIDER_UNAVAILABLE")


class PayloadTooLargeError(AppError):
    def __init__(self, message: str = "Uploaded file is too large") -> None:
        super().__init__(message, status_code=413, error_code="FILE_TOO_LARGE")
