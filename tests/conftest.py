from __future__ import annotations

import base64
import os

import pytest
import pytest_asyncio

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ALLOW_SQLITE_FOR_TESTS", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-tests-123456")
os.environ.setdefault("BIOMETRIC_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"t" * 32).decode())
os.environ.setdefault("FACE_RECOGNITION_PROVIDER", "mock")
os.environ.setdefault("FACE_LIVENESS_PROVIDER", "mock")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("CORS_ORIGINS", "http://localhost")

import httpx  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User, UserRole  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_user(db: Session) -> User:
    user = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password("AdminPassword123!"),
        full_name="System Administrator",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def viewer_user(db: Session) -> User:
    user = User(
        username="viewer",
        email="viewer@example.com",
        password_hash=hash_password("ViewerPassword123!"),
        full_name="Read Only",
        role=UserRole.VIEWER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


async def _login(client: httpx.AsyncClient, username: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["tokens"]


@pytest_asyncio.fixture
async def admin_tokens(client: httpx.AsyncClient, admin_user: User) -> dict:
    return await _login(client, "admin", "AdminPassword123!")


@pytest_asyncio.fixture
async def admin_headers(admin_tokens: dict) -> dict:
    return {"Authorization": f"Bearer {admin_tokens['access_token']}"}


@pytest_asyncio.fixture
async def viewer_headers(client: httpx.AsyncClient, viewer_user: User) -> dict:
    tokens = await _login(client, "viewer", "ViewerPassword123!")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def kiosk(client: httpx.AsyncClient, admin_headers: dict) -> dict:
    response = await client.post(
        "/api/v1/kiosks",
        headers=admin_headers,
        json={"kiosk_code": "KIOSK-01", "device_name": "Lobby Kiosk", "location": "Lobby"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest_asyncio.fixture
async def kiosk_headers(kiosk: dict) -> dict:
    return {"X-Kiosk-Token": kiosk["device_token"]}
