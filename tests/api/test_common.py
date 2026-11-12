from __future__ import annotations


async def test_security_headers_and_request_id(client):
    response = await client.get("/health", headers={"X-Request-ID": "test-request-id"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Content-Security-Policy" in response.headers


async def test_request_id_is_generated_when_missing(client):
    response = await client.get("/health")
    assert response.headers.get("X-Request-ID")


async def test_validation_error_envelope(client):
    response = await client.post("/api/v1/auth/login", json={"username": "only"})
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert payload["details"]
    assert payload["message"] == "Request validation failed"


async def test_cors_preflight(client):
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost"


async def test_root_and_not_found(client):
    root = await client.get("/")
    assert root.status_code == 200
    assert root.json()["data"]["api_prefix"] == "/api/v1"

    missing = await client.get("/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "HTTP_404"
