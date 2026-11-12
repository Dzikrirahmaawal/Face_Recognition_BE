# Smart Visitor Attendance API

Backend-only visitor attendance platform with face enrollment, face identification, liveness checks, attendance tracking, reporting, audit logging, and privacy controls. The required production database is **Microsoft SQL Server**; SQLite is accepted only by the automated test harness.

The repository also contains a separate, development-only camera client in `devtools/camera-client/` for exercising the flow from a browser.

## Contents

- [Architecture](#architecture)
- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Docker Compose](#docker-compose)
- [Configuration](#configuration)
- [Roles and permissions](#roles-and-permissions)
- [API overview](#api-overview)
- [Face providers and licensing](#face-providers-and-licensing)
- [Privacy and biometric data](#privacy-and-biometric-data)
- [Attendance safety](#attendance-safety)
- [Retention](#retention)
- [Testing](#testing)
- [Production checklist](#production-checklist)
- [Verification status and limitations](#verification-status-and-limitations)

## Architecture

```text
Browser / kiosk / camera client
              |
              v
        FastAPI /api/v1
              |
    +---------+----------+
    |                    |
Auth + RBAC         Face pipeline
    |                    |
    +---------+----------+
              |
        Service layer
              |
        SQLAlchemy 2.0
              |
        Microsoft SQL Server
```

Key decisions:

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic.
- UUID primary keys generated in Python; `UNIQUEIDENTIFIER` on SQL Server and `CHAR(36)` in tests.
- UTC timestamps stored with timezone awareness; business reporting uses `Asia/Jakarta`.
- Enumerations stored as `NVARCHAR` values, not database-native enums.
- API responses use a consistent envelope:

```json
{
  "success": true,
  "message": "Human readable message",
  "data": {},
  "meta": null
}
```

Errors use `error_code` and optional `details` instead of leaking internals.

## Features

- JWT access tokens and rotating refresh tokens with reuse detection.
- Argon2id password hashing and password-strength validation.
- Role-based access control for super admins, admins, receptionists, security staff, and viewers.
- Visitor registration, search, update, soft deletion, and identity uniqueness.
- Face enrollment, identification, verification, duplicate detection, quality checks, and liveness checks.
- AES-256-GCM encryption for biometric embeddings at rest.
- Consent capture, withdrawal, biometric deletion, and consent history.
- Kiosk device tokens hashed with HMAC-SHA256.
- Attendance check-in/check-out with duplicate prevention and idempotency.
- Append-only attendance corrections.
- Visit lifecycle management and host employee validation.
- Daily, monthly, dashboard, and visitor reports with CSV/XLSX export.
- Audit logging for security and administrative actions.
- Request IDs, security headers, CORS, rate limiting, and health/readiness endpoints.
- Configurable retention job and SQL Server integration tests.

## Requirements

- Python 3.12+
- Microsoft SQL Server 2019/2022 (development and production)
- Microsoft ODBC Driver 18 for SQL Server
- Optional: Docker and Docker Compose
- Optional for real recognition: `insightface` and `onnxruntime`, plus a licensed model

On Debian/Ubuntu, the ODBC driver is available from Microsoft's package repository. Install `msodbcsql18` and `unixodbc`. The `pyodbc` Python package requires the ODBC driver at runtime.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env. Generate SECRET_KEY and BIOMETRIC_ENCRYPTION_KEY (commands below).

# Create the database if it does not exist, then run migrations:
python scripts/create_database.py
alembic upgrade head

# Create the first administrator:
python scripts/create_superadmin.py \
  --username admin \
  --email admin@example.com \
  --full-name "System Administrator"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Generate secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Open:

- Swagger UI: <http://localhost:8000/docs> (development only)
- Health: <http://localhost:8000/health>
- Readiness: <http://localhost:8000/ready>

The application intentionally refuses to start with SQLite outside `APP_ENV=test` and `ALLOW_SQLITE_FOR_TESTS=true`.

## Docker Compose

`docker-compose.yml` runs SQL Server 2022 and the API. It is a **development** setup: it enables the mock face/liveness providers and uses `TrustServerCertificate=yes` for the local container certificate.

```bash
cp .env.example .env
# Set a strong MSSQL_SA_PASSWORD and the application secrets in .env.
docker compose up --build
```

The app container creates the database if needed, runs `alembic upgrade head`, then starts Uvicorn. The SQL Server volume persists in `mssql_data`.

For production, do not reuse the compose defaults: use a trusted SQL Server certificate, non-mock providers, a strong secret, a managed biometric key, and a production-grade process manager or container platform.

## Configuration

Configuration is loaded from environment variables and `.env`. See `.env.example` for the full list.

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development`, `test`, or `production` |
| `SECRET_KEY` | JWT signing and kiosk-token HMAC key; must be strong in production |
| `DATABASE_URL` | Must be `mssql+pyodbc://...` in production |
| `CORS_ORIGINS` | Comma-separated allowed browser origins; wildcard rejected in production |
| `FACE_RECOGNITION_PROVIDER` | `mock`, `insightface`, or `disabled` |
| `FACE_MODEL_PATH` | Required when using InsightFace |
| `FACE_LIVENESS_PROVIDER` | `mock`, `http`, or `disabled` |
| `FACE_LIVENESS_URL` | Required for the HTTP liveness adapter |
| `BIOMETRIC_ENCRYPTION_KEY` | URL-safe base64 of exactly 32 bytes; required in production |
| `VISITOR_RETENTION_DAYS` | Biometric retention window for inactive visitors |
| `ATTENDANCE_RETENTION_DAYS` | Attendance-log retention window |
| `RATE_LIMIT_ENABLED` | Enables the in-process rate limiter |
| `ALLOW_SQLITE_FOR_TESTS` | Test-only SQLite gate; never enable in production |

Production validation rejects:

- `DEBUG=true`
- default or short `SECRET_KEY`
- non-SQL Server database URLs
- `TrustServerCertificate=yes`
- wildcard CORS
- mock or disabled face/liveness providers
- missing InsightFace model path
- missing or invalid biometric key
- SQLite without the test-only flags

## Roles and permissions

| Permission area | SUPER_ADMIN | ADMIN | RECEPTIONIST | SECURITY | VIEWER |
| --- | --- | --- | --- | --- | --- |
| User management | yes | no | no | no | no |
| Kiosk management | yes | no | no | no | no |
| Kiosk read | yes | yes | yes | yes | no |
| Visitor read | yes | yes | yes | yes | yes |
| Visitor write/delete | yes | write + delete | write | no | no |
| Face enroll | yes | yes | yes | no | no |
| Face identify/verify | yes | yes | yes | yes | no |
| Face delete | yes | yes | no | no | no |
| Attendance read/write | yes | yes | yes | yes | read |
| Attendance correction | yes | yes | no | no | no |
| Visit read/write | yes | yes | yes | read | read |
| Employee read/write | yes | yes | read | no | no |
| Reports | yes | yes | no | no | yes |
| Audit logs | yes | yes | no | no | no |
| Privacy management | yes | yes | no | no | no |

## API overview

All application endpoints are under `/api/v1`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` |
| Visitors | `GET/POST /visitors`, `GET/PUT/DELETE /visitors/{id}` |
| Privacy | `POST /visitors/{id}/biometric/withdraw`, `DELETE /visitors/{id}/biometric`, `GET /visitors/{id}/consents` |
| Face | `POST /face/enroll`, `POST /face/identify`, `POST /face/verify`, `POST /face/liveness`, `DELETE /face/profiles/{id}` |
| Attendance | `POST /attendance/check-in`, `POST /attendance/check-out`, `GET /attendance`, `GET /attendance/{id}` |
| Visits | `GET/POST /visits`, `GET/PUT /visits/{id}`, `POST /visits/{id}/cancel` |
| Employees | `GET/POST /employees`, `GET/PUT/DELETE /employees/{id}` |
| Reports | `GET /reports/dashboard`, daily/monthly/visitor reports, `GET /reports/attendance/export` |
| Kiosks | `GET/POST /kiosks`, `GET /kiosks/{id}`, `PATCH /kiosks/{id}/status` |
| Administration | `GET/POST /admin/users`, `PATCH /admin/users/{id}`, `GET /admin/audit-logs`, `POST /admin/attendance/{id}/correct` |

Kiosk-authenticated endpoints accept `X-Kiosk-Token`. Staff endpoints accept `Authorization: Bearer <access_token>`. Attendance write endpoints accept either.

### Idempotency

Send `Idempotency-Key` on attendance writes. Reusing a key with the same payload returns the original response; reusing it with a different payload returns `409 IDEMPOTENCY_KEY_REUSED`.

### Corrections

Attendance corrections append a new record with `is_correction=true` and `correction_of_id`. Changing an event type is intentionally unsupported (`422 UNSUPPORTED_CORRECTION`); cancel and create a new visit instead.

## Face providers and licensing

The default `mock` provider is deterministic and intended only for development and automated tests. It does not perform real face recognition. Production startup rejects it.

The optional `insightface` adapter is a thin integration layer. InsightFace code and pretrained models have their own license terms. Public availability does not imply commercial permission. The deploying organization must verify model and library licensing, provenance, and permitted use before enabling it.

The HTTP liveness adapter expects a commercially licensed external service:

```text
POST multipart/form-data with field "image" (JPEG)
Optional Authorization: Bearer <FACE_LIVENESS_API_KEY>
Response JSON: {"passed": true, "score": 0.98, "reason": null}
```

No real face-recognition model or liveness model is bundled with this repository.

## Privacy and biometric data

- Enrollment requires explicit biometric consent.
- Embeddings are encrypted with AES-256-GCM before storage.
- Embeddings and encryption keys are never returned by APIs or written to logs.
- Consent withdrawal and biometric deletion deactivate profiles and clear stored embeddings.
- Attendance history is retained after biometric deletion.
- Kiosk tokens are stored only as HMAC hashes.
- Refresh tokens are stored only as SHA-256 hashes.
- Audit logs record security-relevant actions without embedding values or secrets.
- Reports and API responses expose visitor summaries, not biometric vectors.

The system provides the technical controls; the deploying organization remains responsible for its privacy notice, lawful basis, consent language, retention schedule, and data-subject request process.

## Attendance safety

- A visitor can have at most one active visit.
- A visit can have at most one original CHECK_IN and one original CHECK_OUT.
- SQL Server filtered unique indexes enforce these rules even under concurrent requests.
- Active visit and attendance event uniqueness are also represented in the SQLAlchemy models with SQLite-specific index predicates for the test harness.
- Attendance writes lock the visitor/visit row where supported and translate unique-constraint races into `409` conflicts.
- Idempotency keys make client retries safe.

## Retention

Run the retention maintenance job from cron, systemd, or a scheduled container:

```bash
# Preview only:
python scripts/purge_expired_data.py --dry-run

# Apply:
python scripts/purge_expired_data.py --yes
```

The job:

- clears biometric embeddings for inactive visitors past `VISITOR_RETENTION_DAYS`,
- deletes expired idempotency records,
- deletes expired refresh tokens,
- deletes attendance logs past `ATTENDANCE_RETENTION_DAYS`, respecting correction references.

Dry-run mode rolls back all changes after reporting counts.

## Testing

```bash
pytest
```

The default suite uses an in-memory SQLite database with `StaticPool`, mock face/liveness providers, and a test-only biometric key. It covers authentication, refresh rotation and reuse detection, RBAC, visitor/employee/kiosk/visit CRUD, face enrollment/identification/duplicate/quality cases, liveness, attendance duplicates and idempotency, corrections, consent withdrawal, biometric deletion, reports and exports, audit logs, security headers, retention, and unit-level security/config/face-engine behavior.

### SQL Server integration tests

These are skipped unless explicitly configured because they run migrations and are destructive:

```bash
export TEST_DATABASE_URL='mssql+pyodbc://sa:Password@localhost:1433/visitor_attendance_test?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes'
export ALLOW_SQLSERVER_INTEGRATION_TESTS=true
pytest -m sqlserver
```

Use a dedicated test database. The integration suite runs `alembic upgrade head`, verifies tables and filtered indexes, checks active-visit/face-profile/attendance-event unique constraints, tests a concurrent check-in, and then runs `alembic downgrade base`.

If the ODBC driver is installed user-locally instead of system-wide (for example, because `sudo` is unavailable), point the loader at it before running Alembic or pytest:

```bash
export LD_LIBRARY_PATH="$HOME/.local/msodbcsql18/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ODBCSYSINI="$HOME/.local/msodbcsql18/etc"
```

## Production checklist

- [ ] Use SQL Server with a trusted TLS certificate; do not use `TrustServerCertificate=yes`.
- [ ] Set a strong random `SECRET_KEY` and a separately managed 32-byte biometric key.
- [ ] Use a non-mock face provider and a licensed liveness provider.
- [ ] Verify provider/model licensing and data-processing terms.
- [ ] Restrict CORS to known browser origins.
- [ ] Terminate TLS at a reverse proxy or load balancer.
- [ ] Run Alembic migrations before starting the app.
- [ ] Run the retention job on a schedule.
- [ ] Configure database backups and restore tests.
- [ ] Run multiple app workers only with a shared rate-limit store; the built-in limiter is per-process.
- [ ] Disable Swagger/OpenAPI exposure in production (automatic when `APP_ENV=production`).
- [ ] Monitor `/health` and `/ready`; readiness fails when the database or configured providers are unavailable.
- [ ] Restrict kiosk tokens to kiosk devices and rotate them after loss.
- [ ] Review audit logs and consent records as part of operations.

## Verification status and limitations

Verified locally:

- Application imports and compiles under the test configuration.
- The automated API/unit test suite passes against SQLite with mock providers (98 passed, 1 SQL Server test module skipped).
- Microsoft SQL Server 2022 Developer Edition runs via Docker Compose, and the API connects through `pyodbc` with Microsoft ODBC Driver 18.
- Alembic reports the main database at `0001_initial_schema (head)`, and `alembic check` reports no pending upgrade operations.
- The SQL Server integration suite passes (schema and filtered indexes, unique constraints, concurrent check-in) and downgrades the dedicated test database cleanly (6 passed).
- A Docker image containing Microsoft ODBC Driver 18 was built and used to validate database connectivity.
- The development camera client is dependency-free and served as static files.

Not verified in this environment:

- **Real face recognition and liveness accuracy.** No real model or licensed liveness service is bundled. Mock providers only validate workflow behavior. Thresholds must be calibrated against the chosen provider and real data.
- **Production deployment hardening.** Local validation uses the development compose configuration (`TrustServerCertificate=yes`, mock providers, container-managed secrets). Trusted TLS certificates, licensed providers, and external secret management must be configured and verified before production.
- **Multi-process rate limiting.** The built-in limiter is in-memory and intended for a single process; use a shared store for horizontally scaled deployments.
