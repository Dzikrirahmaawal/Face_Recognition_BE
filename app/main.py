from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.face_engine.factory import get_face_provider, get_liveness_provider
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware, SecurityHeadersMiddleware
from app.schemas.common import error_payload

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(
        "Starting application",
        extra={"extra_data": {"app": settings.APP_NAME, "env": settings.APP_ENV, "version": settings.APP_VERSION}},
    )
    try:
        face_provider = get_face_provider()
        liveness_provider = get_liveness_provider()
        logger.info(
            "Face providers configured",
            extra={
                "extra_data": {
                    "face_provider": face_provider.name,
                    "model_version": face_provider.model_version,
                    "liveness_provider": liveness_provider.name,
                }
            },
        )
        if settings.is_production:
            if not face_provider.is_available():
                raise RuntimeError("Configured face recognition provider is unavailable")
            if not liveness_provider.is_available():
                raise RuntimeError("Configured liveness provider is unavailable")
    except Exception:
        if settings.is_production:
            raise
        logger.warning("Face provider validation skipped/failed in non-production environment", exc_info=True)
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend API for Smart Visitor Attendance using face recognition. "
        "Biometric embeddings are never returned by any endpoint."
    ),
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

origins = settings.cors_origins
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Kiosk-Token", "X-Request-ID", "Idempotency-Key"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

app.include_router(health.router)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return {
        "success": True,
        "message": settings.APP_NAME,
        "data": {
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "docs": "/docs" if not settings.is_production else None,
            "api_prefix": settings.API_V1_PREFIX,
        },
        "meta": None,
    }


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.message, exc.error_code, exc.details),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [
        {
            "location": ".".join(str(part) for part in error.get("loc", [])),
            "message": error.get("msg"),
            "type": error.get("type"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_payload("Request validation failed", "VALIDATION_ERROR", details),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(str(exc.detail), f"HTTP_{exc.status_code}", None),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content=error_payload(
            "A database error occurred. Please try again later.",
            "DATABASE_ERROR",
            None,
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content=error_payload(
            "An internal error occurred. Please try again later.",
            "INTERNAL_ERROR",
            None,
        ),
    )
