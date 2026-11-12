from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-change-this-secret-key-before-any-real-deployment"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Smart Visitor Attendance API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = DEV_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "smart-visitor-attendance"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = (
        "mssql+pyodbc://sa:Your_password123@localhost/visitor_attendance"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes"
    )
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    CORS_ORIGINS: str = "http://localhost:8080,http://127.0.0.1:8080"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp"

    FACE_RECOGNITION_PROVIDER: Literal["mock", "insightface", "disabled"] = "mock"
    FACE_MODEL_PATH: str = ""
    FACE_MODEL_VERSION: str = "mock-v1"
    FACE_EMBEDDING_VERSION: str = "1"
    FACE_MATCH_THRESHOLD: float = 0.60
    FACE_REVIEW_THRESHOLD: float = 0.45
    FACE_DUPLICATE_THRESHOLD: float = 0.80
    FACE_AMBIGUITY_MARGIN: float = 0.05
    FACE_MIN_FACE_SIZE: int = 80
    FACE_MIN_BLUR_SCORE: float = 40.0
    FACE_MIN_BRIGHTNESS: float = 30.0
    FACE_MAX_BRIGHTNESS: float = 230.0
    FACE_MAX_IMAGE_PIXELS: int = 25_000_000

    FACE_LIVENESS_PROVIDER: Literal["mock", "http", "disabled"] = "mock"
    FACE_LIVENESS_URL: str = ""
    FACE_LIVENESS_API_KEY: str = ""
    FACE_LIVENESS_TIMEOUT_SECONDS: float = 10.0

    BIOMETRIC_ENCRYPTION_KEY: str = ""

    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: int = 10
    LOGIN_RATE_WINDOW_SECONDS: int = 60
    GLOBAL_RATE_LIMIT: int = 300
    GLOBAL_RATE_WINDOW_SECONDS: int = 60

    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Asia/Jakarta"
    IDEMPOTENCY_TTL_HOURS: int = 24
    KIOSK_LAST_SEEN_UPDATE_SECONDS: int = 60

    VISITOR_RETENTION_DAYS: int = 365
    ATTENDANCE_RETENTION_DAYS: int = 1095
    ALLOW_SQLITE_FOR_TESTS: bool = False

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _strip_cors(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]

    @property
    def allowed_image_types(self) -> set[str]:
        return {item.strip().lower() for item in self.ALLOWED_IMAGE_TYPES.split(",") if item.strip()}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def biometric_key(self) -> bytes:
        if self.BIOMETRIC_ENCRYPTION_KEY:
            try:
                raw = base64.urlsafe_b64decode(self.BIOMETRIC_ENCRYPTION_KEY.encode())
            except Exception as exc:  # pragma: no cover - defensive
                raise ValueError("BIOMETRIC_ENCRYPTION_KEY must be URL-safe base64") from exc
            if len(raw) != 32:
                raise ValueError("BIOMETRIC_ENCRYPTION_KEY must decode to exactly 32 bytes")
            return raw
        if self.is_production:
            raise ValueError("BIOMETRIC_ENCRYPTION_KEY is required in production")
        return hashlib.sha256(f"dev-biometric::{self.SECRET_KEY}".encode()).digest()

    @property
    def database_is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @model_validator(mode="after")
    def _validate_environment(self) -> "Settings":
        if self.is_production:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if self.SECRET_KEY == DEV_SECRET or len(self.SECRET_KEY) < 32:
                raise ValueError("A strong SECRET_KEY (>=32 chars) is required in production")
            if not self.DATABASE_URL.startswith("mssql+pyodbc://"):
                raise ValueError("Production DATABASE_URL must use mssql+pyodbc")
            if "trustservercertificate=yes" in self.DATABASE_URL.lower():
                raise ValueError(
                    "TrustServerCertificate=yes is not allowed in production; configure a trusted TLS certificate"
                )
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
            if self.FACE_RECOGNITION_PROVIDER in {"mock", "disabled"}:
                raise ValueError("A licensed, non-mock face recognition provider is required in production")
            if self.FACE_LIVENESS_PROVIDER in {"mock", "disabled"}:
                raise ValueError("A non-mock liveness provider is required in production")
            if self.FACE_RECOGNITION_PROVIDER == "insightface" and not self.FACE_MODEL_PATH:
                raise ValueError("FACE_MODEL_PATH is required for the insightface provider")
            if not self.BIOMETRIC_ENCRYPTION_KEY:
                raise ValueError("BIOMETRIC_ENCRYPTION_KEY is required in production")
            self.biometric_key  # validate decodes to 32 bytes
        if self.database_is_sqlite and not (self.APP_ENV == "test" and self.ALLOW_SQLITE_FOR_TESTS):
            raise ValueError(
                "SQLite is only permitted for automated tests (APP_ENV=test and ALLOW_SQLITE_FOR_TESTS=true). "
                "Use Microsoft SQL Server for development and production."
            )
        if self.FACE_LIVENESS_PROVIDER == "http" and not self.FACE_LIVENESS_URL:
            raise ValueError("FACE_LIVENESS_URL is required when FACE_LIVENESS_PROVIDER=http")
        if self.FACE_REVIEW_THRESHOLD > self.FACE_MATCH_THRESHOLD:
            raise ValueError("FACE_REVIEW_THRESHOLD must be <= FACE_MATCH_THRESHOLD")
        if self.FACE_DUPLICATE_THRESHOLD < self.FACE_MATCH_THRESHOLD:
            raise ValueError("FACE_DUPLICATE_THRESHOLD must be >= FACE_MATCH_THRESHOLD")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
