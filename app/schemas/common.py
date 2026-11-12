from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PaginationMeta


class MessageResponse(BaseModel):
    message: str


class IdempotencyHeader(BaseModel):
    idempotency_key: str | None = Field(default=None, max_length=128)


def success_payload(data: Any = None, message: str = "OK", meta: Any = None) -> dict[str, Any]:
    return {"success": True, "message": message, "data": data, "meta": meta}


def pagination_meta(page: int, page_size: int, total: int) -> dict[str, int]:
    page = max(1, page)
    page_size = max(1, page_size)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
    }


def error_payload(message: str, error_code: str, details: Any = None) -> dict[str, Any]:
    return {"success": False, "message": message, "error_code": error_code, "details": details}
