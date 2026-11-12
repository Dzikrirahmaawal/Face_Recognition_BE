from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from app.core.config import DEV_SECRET, Settings

BIOMETRIC_KEY = base64.urlsafe_b64encode(b"k" * 32).decode()
SQLSERVER_URL = (
    "mssql+pyodbc://sa:Password123@db.example.com/visitor_attendance"
    "?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes"
)


def production_settings(**overrides) -> Settings:
    values = {
        "APP_ENV": "production",
        "SECRET_KEY": "a-very-long-production-secret-key-1234567890",
        "DATABASE_URL": SQLSERVER_URL,
        "CORS_ORIGINS": "https://attendance.example.com",
        "FACE_RECOGNITION_PROVIDER": "insightface",
        "FACE_MODEL_PATH": "/models/insightface",
        "FACE_LIVENESS_PROVIDER": "http",
        "FACE_LIVENESS_URL": "https://liveness.example.com/verify",
        "BIOMETRIC_ENCRYPTION_KEY": BIOMETRIC_KEY,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_configuration():
    settings = production_settings()
    assert settings.is_production is True
    assert settings.biometric_key == b"k" * 32
    assert settings.database_is_sqlite is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"SECRET_KEY": DEV_SECRET}, "SECRET_KEY"),
        ({"SECRET_KEY": "short"}, "SECRET_KEY"),
        ({"DATABASE_URL": "sqlite:///prod.db"}, "mssql+pyodbc"),
        (
            {
                "DATABASE_URL": SQLSERVER_URL + "&TrustServerCertificate=yes",
            },
            "TrustServerCertificate",
        ),
        ({"CORS_ORIGINS": "*"}, "Wildcard CORS"),
        ({"FACE_RECOGNITION_PROVIDER": "mock"}, "non-mock face"),
        ({"FACE_LIVENESS_PROVIDER": "mock"}, "non-mock liveness"),
        ({"FACE_MODEL_PATH": ""}, "FACE_MODEL_PATH"),
        ({"BIOMETRIC_ENCRYPTION_KEY": ""}, "BIOMETRIC_ENCRYPTION_KEY"),
        (
            {"BIOMETRIC_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"short").decode()},
            "32 bytes",
        ),
    ],
)
def test_production_configuration_rejections(overrides, message):
    with pytest.raises(ValidationError) as exc:
        production_settings(**overrides)
    assert message in str(exc.value)


def test_sqlite_is_rejected_outside_tests():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, APP_ENV="development", DATABASE_URL="sqlite:///local.db")
    assert "SQLite is only permitted" in str(exc.value)


def test_sqlite_is_allowed_in_tests():
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        ALLOW_SQLITE_FOR_TESTS=True,
        DATABASE_URL="sqlite:///:memory:",
    )
    assert settings.database_is_sqlite is True


def test_threshold_ordering_is_enforced():
    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            FACE_REVIEW_THRESHOLD=0.9,
            FACE_MATCH_THRESHOLD=0.6,
        )
    assert "FACE_REVIEW_THRESHOLD" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            FACE_DUPLICATE_THRESHOLD=0.5,
            FACE_MATCH_THRESHOLD=0.6,
        )
    assert "FACE_DUPLICATE_THRESHOLD" in str(exc.value)


def test_http_liveness_requires_url():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, FACE_LIVENESS_PROVIDER="http", FACE_LIVENESS_URL="")
    assert "FACE_LIVENESS_URL" in str(exc.value)
