# Frontend API Reference

Regenerated from the current backend source under `app/` and verified against a
live instance (`GET /openapi.json`, `GET /health`, `GET /ready`) on 2026-11-11.
This document supersedes earlier revisions; it reflects the code as it exists
today, including the current reporting implementation.

- Base URL (local): `http://127.0.0.1:8000`
- API prefix: `/api/v1`
- OpenAPI: `GET /openapi.json` (development only; disabled when `APP_ENV=production`)
- Swagger UI: `GET /docs` (development only)
- ReDoc: `GET /redoc` (development only)
- Content type: `application/json` except face endpoints (`multipart/form-data`)
  and report export (file download)
- Timestamps: ISO-8601, UTC (`Z` / `+00:00` suffix)
- IDs: UUID strings
- Report date boundaries use the configured business timezone (`Asia/Jakarta`)
- Live OpenAPI version: 3.1.0, **47 operations across 37 paths**

> Security note: OpenAPI marks only `HTTPBearer` as a security scheme. Face,
> attendance check-in/check-out, and attendance correction use a custom
> dependency, so their OpenAPI operations show `security: null`. They still
> require `Authorization: Bearer <access_token>` or `X-Kiosk-Token: <device_token>`.
> Do not trust the Swagger padlock for those operations.

## Authentication

### Staff (JWT bearer)

1. `POST /api/v1/auth/login` with `{ "username": "<username-or-email>", "password": "<password>" }`.
   `username` accepts either the username or the email address.
2. Store `data.tokens.access_token` in memory and `data.tokens.refresh_token` securely.
3. Send `Authorization: Bearer <access_token>` on staff endpoints.
4. Access tokens expire in 15 minutes; refresh tokens in 7 days (configurable
   via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` / `JWT_REFRESH_TOKEN_EXPIRE_DAYS`).
   `expires_in` in the token pair is the access-token lifetime in seconds (900).
5. `POST /api/v1/auth/refresh` **rotates** the refresh token: the old token is
   revoked and replaced. Reusing an already-rotated refresh token revokes all
   sessions for the user (`REFRESH_TOKEN_REUSED`) — treat it as force-logout.
6. `POST /api/v1/auth/logout` revokes the supplied refresh token, or all
   sessions when `all_devices` is `true` (bumps the user's `token_version`).
7. Passwords are Argon2id-hashed; creation/update enforces a minimum length of
   12 plus lowercase, uppercase, digit, and special character requirements.
8. Changing a user's password, role, or active state (via
   `PATCH /admin/users/{id}`) bumps `token_version`, revoking all their tokens.

JWT claims issued: `sub` (user UUID), `role`, `tv` (token version), `type`
(`access` / `refresh`), `iss`, `iat`, `nbf`, `exp`, `jti`. Only access tokens
are accepted by bearer-protected endpoints.

### Kiosk device (opaque token)

1. A SUPER_ADMIN creates a kiosk via `POST /api/v1/kiosks`.
2. The response contains `data.device_token` exactly once (format
   `kiosk_<random>`). Store it on the device.
3. Send `X-Kiosk-Token: <device_token>` (do not also send a bearer token — the
   kiosk header takes priority over `Authorization` when both are present).
4. Kiosk tokens are accepted **only** by:
   - `POST /api/v1/face/enroll`
   - `POST /api/v1/face/identify`
   - `POST /api/v1/face/verify`
   - `POST /api/v1/face/liveness`
   - `POST /api/v1/attendance/check-in`
   - `POST /api/v1/attendance/check-out`
5. Kiosks bypass role permission checks on those operations but are still
   subject to kiosk active-state checks (`INVALID_KIOSK_TOKEN`,
   `KIOSK_DISABLED`) and `kiosk_id` matching (`KIOSK_MISMATCH`).
6. Attendance correction is staff-only (`allow_kiosk=False`). Face profile
   deletion and all list/CRUD endpoints require a staff JWT.
7. `last_seen_at` is refreshed (at most once per 60 s) on any kiosk-authenticated
   request; there is no explicit heartbeat endpoint.

### Login response shape

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "user": {
      "id": "00000000-0000-0000-0000-000000000000",
      "username": "<username>",
      "email": "<email>",
      "full_name": "<full name>",
      "role": "ADMIN",
      "is_active": true,
      "last_login_at": "2026-11-11T03:00:00+00:00",
      "created_at": "2026-01-01T00:00:00+00:00"
    },
    "tokens": {
      "access_token": "<access_token>",
      "refresh_token": "<refresh_token>",
      "token_type": "bearer",
      "expires_in": 900
    }
  },
  "meta": null
}
```

`POST /auth/refresh` returns the same shape with message `Token refreshed`.

## Response envelope

Success:

```json
{ "success": true, "message": "OK", "data": {}, "meta": null }
```

Paginated success:

```json
{
  "success": true,
  "message": "Visitors retrieved",
  "data": [],
  "meta": { "page": 1, "page_size": 20, "total": 0, "total_pages": 0 }
}
```

Error:

```json
{
  "success": false,
  "message": "Authentication required",
  "error_code": "UNAUTHORIZED",
  "details": null
}
```

Validation error (`422`):

```json
{
  "success": false,
  "message": "Request validation failed",
  "error_code": "VALIDATION_ERROR",
  "details": [
    { "location": "body.username", "message": "Field required", "type": "missing" }
  ]
}
```

`GET /ready` when not ready returns `503` with the standard success-shaped
body where `success: false` and `data.ready: false` (no `error_code` field).

## Headers

| Header | Required | Used by | Notes |
| --- | --- | --- | --- |
| `Authorization: Bearer <jwt>` | Staff endpoints | All staff operations | Access token |
| `X-Kiosk-Token: <token>` | Kiosk endpoints | Face + attendance check-in/out | Takes priority over bearer |
| `Content-Type: application/json` | JSON bodies | Most writes | — |
| `Content-Type: multipart/form-data` | Face endpoints | `enroll`, `identify`, `verify`, `liveness` | Image field name is `image` |
| `Idempotency-Key` | Optional | `attendance/check-in`, `attendance/check-out` | Max 128 chars; replay returns cached status/body |
| `X-Request-ID` | Optional | All | Echoed back; generated when absent |
| `Accept: text/csv` / `application/vnd...` | Optional | Report export | Server sets `Content-Disposition` |

Every response also carries security headers: `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
`Permissions-Policy: camera=(self)`, `Cache-Control: no-store`, and a CSP.
Do not cache API responses client-side.

CORS (verified live): allowed origins in the current development configuration
are `http://localhost:8080`, `http://127.0.0.1:8080`, `http://localhost:5173`,
and `http://localhost:8081`; methods `GET, POST, PUT, PATCH, DELETE, OPTIONS`;
allowed request headers `Authorization, Content-Type, X-Kiosk-Token,
X-Request-ID, Idempotency-Key` (plus the browser defaults `Accept`,
`Accept-Language`, `Content-Language`); response exposes `X-Request-ID`;
credentials allowed; preflight max age 600 s. Wildcard origins are rejected in
production configuration.

## Pagination and filtering

- `page` default `1`, minimum `1`.
- `page_size` default `20`, min `1`, max `200` (server also clamps to 200).
- Response `data` is the item array and `meta` is
  `{ page, page_size, total, total_pages }`.
- `total_pages` is `ceil(total / page_size)`; it is `0` when `total` is `0`.
- List filters are documented per endpoint below.
- `search` is a partial text match, max length 150.

## Status codes and error codes

Codes implemented in the current backend, grouped by HTTP status:

| HTTP | Meaning | `error_code` values |
| --- | --- | --- |
| 200 | Success | — |
| 201 | Created / check-in | — |
| 400 | Business rule violation | `BAD_REQUEST` |
| 401 | Missing/invalid auth | `UNAUTHORIZED`, `INVALID_CREDENTIALS`, `INVALID_TOKEN`, `INVALID_REFRESH_TOKEN`, `REFRESH_TOKEN_EXPIRED`, `REFRESH_TOKEN_REUSED`, `TOKEN_REVOKED`, `ACCOUNT_DISABLED`, `INVALID_KIOSK_TOKEN`, `KIOSK_DISABLED` |
| 403 | Permission/consent denied | `FORBIDDEN`, `KIOSK_MISMATCH`, `BIOMETRIC_AUTHORIZATION_REQUIRED` (attendance writes) |
| 404 | Not found | `NOT_FOUND`, `VISITOR_NOT_FOUND`, `VISIT_NOT_FOUND`, `ATTENDANCE_NOT_FOUND`, `EMPLOYEE_NOT_FOUND`, `HOST_EMPLOYEE_NOT_FOUND`, `KIOSK_NOT_FOUND`, `USER_NOT_FOUND`, `FACE_PROFILE_NOT_FOUND` |
| 409 | State/unique conflict | `CONFLICT`, `VISITOR_INACTIVE`, `VISITOR_EXISTS`, `VISITOR_CONFLICT`, `VISITOR_CODE_EXHAUSTED`, `VISIT_VISITOR_MISMATCH`, `VISIT_NOT_ACTIVE`, `VISIT_NOT_EDITABLE`, `VISIT_ALREADY_CANCELLED`, `VISIT_ALREADY_CLOSED`, `VISIT_CHECKOUT_REQUIRED`, `ALREADY_CHECKED_IN`, `ALREADY_CHECKED_OUT`, `NOT_CHECKED_IN`, `NO_ACTIVE_VISIT`, `ACTIVE_VISIT_EXISTS`, `DUPLICATE_ATTENDANCE`, `INVALID_CORRECTION_TARGET`, `HOST_EMPLOYEE_INACTIVE`, `EMPLOYEE_CODE_EXISTS`, `EMPLOYEE_EMAIL_EXISTS`, `EMPLOYEE_CONFLICT`, `KIOSK_CODE_EXISTS`, `KIOSK_CONFLICT`, `KIOSK_INACTIVE`, `USERNAME_EXISTS`, `EMAIL_EXISTS`, `FACE_PROFILE_EXISTS`, `FACE_PROFILE_CONFLICT`, `FACE_DUPLICATE_DETECTED`, `BIOMETRIC_AUTHORIZATION_REQUIRED` (face verify), `IDEMPOTENCY_KEY_CONFLICT`, `IDEMPOTENCY_KEY_REUSED` |
| 413 | Upload too large | `FILE_TOO_LARGE` |
| 422 | Validation/business validation | `VALIDATION_ERROR`, `CONSENT_REQUIRED`, `VISITOR_NAME_REQUIRED`, `REASON_REQUIRED`, `FACE_QUALITY_REJECTED`, `NO_FACE_DETECTED`, `MULTIPLE_FACES_DETECTED`, `EMPTY_IMAGE`, `INVALID_IMAGE`, `INVALID_IMAGE_FORMAT`, `IMAGE_TOO_SMALL`, `IMAGE_DIMENSIONS_TOO_LARGE`, `IMAGE_TYPE_MISMATCH`, `LIVENESS_FAILED`, `UNSUPPORTED_CORRECTION` |
| 429 | Rate limited | `RATE_LIMITED` + `Retry-After` |
| 500 | Server/DB error | `DATABASE_ERROR`, `INTERNAL_ERROR` |
| 503 | Provider unavailable / not ready | `FACE_PROVIDER_UNAVAILABLE` |

Notes:

- `BIOMETRIC_AUTHORIZATION_REQUIRED` is `403` from attendance writes but `409`
  from `POST /face/verify`.
- `KIOSK_MISMATCH` is `403`; `UNSUPPORTED_CORRECTION` is `422`.
- Unknown routes/methods return the error envelope with `HTTP_404` / `HTTP_405`.

Rate limits (per client IP + path, in-process): login `10` requests / `60 s`;
all other paths `300` / `60 s`. `/health` and `/ready` are exempt. `429`
includes a `Retry-After` header with the retry delay in seconds.

## RBAC permission matrix

Roles: `SUPER_ADMIN`, `ADMIN`, `RECEPTIONIST`, `SECURITY`, `VIEWER`.
Matrix derived from `app/core/permissions.py`:

| Permission | SUPER_ADMIN | ADMIN | RECEPTIONIST | SECURITY | VIEWER |
| --- | --- | --- | --- | --- | --- |
| `user:manage` | yes | no | no | no | no |
| `kiosk:manage` | yes | no | no | no | no |
| `kiosk:read` | yes | yes | yes | yes | no |
| `visitor:read` | yes | yes | yes | yes | yes |
| `visitor:write` | yes | yes | yes | no | no |
| `visitor:delete` | yes | yes | no | no | no |
| `face:enroll` | yes | yes | yes | no | no |
| `face:identify` | yes | yes | yes | yes | no |
| `face:verify` | yes | yes | yes | yes | no |
| `face:delete` | yes | yes | no | no | no |
| `attendance:read` | yes | yes | yes | yes | yes |
| `attendance:write` | yes | yes | yes | yes | no |
| `attendance:correct` | yes | yes | no | no | no |
| `visit:read` | yes | yes | yes | yes | yes |
| `visit:write` | yes | yes | yes | no | no |
| `employee:read` | yes | yes | yes | no | no |
| `employee:write` | yes | yes | no | no | no |
| `report:read` | yes | yes | no | no | yes |
| `audit:read` | yes | yes | no | no | no |
| `privacy:manage` | yes | yes | no | no | no |

Permission failures return `403 FORBIDDEN` with message
`Missing permission: <permission>`.

## Endpoint inventory

All paths below are prefixed with `/api/v1` except `/health` and `/ready`.
47 operations across 37 paths in total (verified against live `/openapi.json`).

### 1. Authentication (4)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | none | — | `LoginRequest` | 200 |
| POST | `/auth/refresh` | none | — | `RefreshRequest` | 200 |
| POST | `/auth/logout` | Bearer | any active user | `LogoutRequest` | 200 |
| GET | `/auth/me` | Bearer | any active user | — | 200 |

```json
// LoginRequest
{ "username": "<username-or-email>", "password": "<password>" }

// RefreshRequest
{ "refresh_token": "<refresh_token>" }

// LogoutRequest
{ "refresh_token": "<refresh_token>", "all_devices": false }

// GET /auth/me data
{ "id": "...", "username": "...", "email": "...", "full_name": "...", "role": "VIEWER", "is_active": true, "last_login_at": null, "created_at": "..." }
```

Business rules: unknown username or wrong password returns `401
INVALID_CREDENTIALS` (same message for both, no user enumeration); disabled
accounts return `401 ACCOUNT_DISABLED`. Refresh with an expired token returns
`401 REFRESH_TOKEN_EXPIRED`; a reused (rotated) token returns `401
REFRESH_TOKEN_REUSED` and revokes every session of that user.

### 2. Health (2, unauthenticated)

| Method | Path | Auth | Success |
| --- | --- | --- | --- |
| GET | `/health` | none | 200 |
| GET | `/ready` | none | 200 ready / 503 not ready |

```json
// /health data
{ "status": "ok", "app": "Smart Visitor Attendance API", "version": "1.0.0", "environment": "development", "timestamp": "..." }

// /ready data
{ "ready": true, "checks": { "database": { "ok": true }, "face_provider": { "ok": true, "name": "mock", "model_version": "mock-v1" }, "liveness_provider": { "ok": true, "name": "mock" } }, "timestamp": "..." }
```

Failed checks include an `error` key with the exception class name. `GET /`
(root, not in the OpenAPI schema) returns basic app metadata.

### 3. Visitor Management (5)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/visitors` | Bearer | `visitor:write` | `VisitorCreate` | 201 |
| GET | `/visitors` | Bearer | `visitor:read` | `page`, `page_size`, `search` (≤150), `is_active` | 200 + meta |
| GET | `/visitors/{visitor_id}` | Bearer | `visitor:read` | path UUID | 200 |
| PUT | `/visitors/{visitor_id}` | Bearer | `visitor:write` | `VisitorUpdate` | 200 |
| DELETE | `/visitors/{visitor_id}` | Bearer | `visitor:delete` | path UUID | 200 (soft deactivate) |

```json
// VisitorCreate
{ "full_name": "<name>", "identity_number": "<optional>", "company_name": "<optional>", "phone_number": "<optional>", "email": "<optional email>" }

// VisitorUpdate
{ "full_name": "<optional>", "identity_number": "<optional>", "company_name": "<optional>", "phone_number": "<optional>", "email": "<optional email>", "is_active": true }

// VisitorOut (data)
{
  "id": "00000000-0000-0000-0000-000000000000",
  "visitor_code": "VIS-20261111-ABCDEF",
  "full_name": "<name>",
  "identity_number": null,
  "company_name": null,
  "phone_number": null,
  "email": null,
  "is_active": true,
  "has_active_face_profile": false,
  "created_at": "2026-11-11T03:00:00+00:00",
  "updated_at": "2026-11-11T03:00:00+00:00"
}
```

Business rules: `visitor_code` is server-generated (`VIS-YYYYMMDD-XXXXXX`);
`identity_number` is unique when provided (`409 VISITOR_EXISTS` on create,
`409 VISITOR_CONFLICT` on update); emails are lowercased. `DELETE /visitors/{id}`
soft-deactivates the visitor and deactivates its active face profiles; history
is retained and the response message states this. A visitor with an inactive
state is rejected by write flows with `409 VISITOR_INACTIVE`.

### 4. Consent Management (3)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/visitors/{visitor_id}/biometric/withdraw` | Bearer | `privacy:manage` | `ConsentWithdrawRequest` | 200 |
| DELETE | `/visitors/{visitor_id}/biometric` | Bearer | `privacy:manage` | body `BiometricDeleteRequest` (DELETE with body) | 200 |
| GET | `/visitors/{visitor_id}/consents` | Bearer | `privacy:manage` | path UUID | 200 |

```json
// ConsentWithdrawRequest
{ "reason": "<optional ≤255>", "policy_version": "<optional ≤50>" }

// BiometricDeleteRequest
{ "reason": "<required 3..255>", "delete_face_profiles": true }

// Consent item (data[])
{
  "id": "00000000-0000-0000-0000-000000000000",
  "consent_type": "BIOMETRIC_PROCESSING",
  "policy_version": "1.0",
  "consent_status": "GRANTED",
  "consented_at": "2026-11-11T03:00:00+00:00",
  "withdrawn_at": null,
  "recorded_by": "00000000-0000-0000-0000-000000000000",
  "created_at": "2026-11-11T03:00:00+00:00"
}
```

There is no standalone "grant consent" endpoint. Consent is recorded during
`POST /face/enroll` via the `consent_granted` and `consent_policy_version`
form fields. Withdraw records a `WITHDRAWN` consent and deactivates active
face profiles (embeddings retained). Biometric deletion clears stored
embeddings (`deleted_at` set) and records a `WITHDRAWN` consent; attendance
history is retained. Consent history is returned as a full array with no
pagination. `consented_at` may be `null` on withdrawal records; `withdrawn_at`
is `null` on granted records.

### 5. Visit Management (5)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/visits` | Bearer | `visit:write` | `VisitCreate` | 201 |
| GET | `/visits` | Bearer | `visit:read` | `page`, `page_size`, `visitor_id`, `status`, `date_from`, `date_to`, `search` (≤150) | 200 + meta |
| GET | `/visits/{visit_id}` | Bearer | `visit:read` | path UUID | 200 |
| PUT | `/visits/{visit_id}` | Bearer | `visit:write` | `VisitUpdate` | 200 |
| POST | `/visits/{visit_id}/cancel` | Bearer | `visit:write` | `VisitCancelRequest` | 200 |

```json
// VisitCreate
{ "visitor_id": "<uuid>", "purpose": "<optional ≤255>", "host_employee_id": "<optional uuid>" }

// VisitUpdate
{ "purpose": "<optional ≤255>", "host_employee_id": "<optional uuid>" }

// VisitCancelRequest
{ "reason": "<optional ≤255>" }

// VisitOut (data)
{
  "id": "00000000-0000-0000-0000-000000000000",
  "visitor_id": "00000000-0000-0000-0000-000000000000",
  "visitor": { "id": "...", "visitor_code": "VIS-...", "full_name": "<name>", "company_name": null },
  "purpose": "<optional>",
  "host_employee_id": null,
  "visit_status": "WAITING",
  "check_in_at": null,
  "check_out_at": null,
  "created_at": "...",
  "updated_at": "..."
}
```

`status` filter values: `WAITING`, `CHECKED_IN`, `CHECKED_OUT`, `CANCELLED`.
`date_from` / `date_to` are datetimes.

Visit state machine (current implementation):

- New visits start as `WAITING`.
- A visitor may have at most one active (`WAITING` or `CHECKED_IN`) visit
  (`409 ACTIVE_VISIT_EXISTS` otherwise, including details
  `{ "visit_id", "visit_status" }`).
- `WAITING -> CHECKED_IN` happens through `POST /attendance/check-in`
  (possibly creating the visit implicitly).
- `CHECKED_IN -> CHECKED_OUT` happens through `POST /attendance/check-out`.
- **Only `WAITING` visits can be cancelled.** Cancelling a `CHECKED_IN` visit
  returns `409 VISIT_CHECKOUT_REQUIRED` (check out first); cancelling a
  `CHECKED_OUT` visit returns `409 VISIT_ALREADY_CLOSED`; cancelling twice
  returns `409 VISIT_ALREADY_CANCELLED`.
- `CHECKED_OUT` and `CANCELLED` visits cannot be edited (`409 VISIT_NOT_EDITABLE`).
- `host_employee_id`, when provided, must reference an active employee
  (`404 HOST_EMPLOYEE_NOT_FOUND`, `409 HOST_EMPLOYEE_INACTIVE`).

### 6. Face Enrollment (2)

| Method | Path | Auth | Permission | Body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/face/enroll` | Bearer or `X-Kiosk-Token` | `face:enroll` (staff only) | multipart | 201 |
| DELETE | `/face/profiles/{profile_id}` | Bearer | `face:delete` | query `delete_biometrics`, `reason` | 200 |

Multipart fields for enroll:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `image` | file | yes | `image/jpeg`, `image/png`, `image/webp`; max 5 MB |
| `visitor_id` | UUID | no | Existing visitor; otherwise create from name fields |
| `full_name` | string | no | Required when no `visitor_id` (`VISITOR_NAME_REQUIRED`) |
| `identity_number` | string | no | ≤64 |
| `company_name` | string | no | ≤150 |
| `phone_number` | string | no | ≤30 |
| `email` | string | no | — |
| `consent_granted` | bool | no (default `true`) | Must be `true`; `false` returns `422 CONSENT_REQUIRED` |
| `consent_policy_version` | string | no (default `"1.0"`) | — |
| `replace_existing` | bool | no (default `false`) | Replace active profile |

```json
// enroll data
{
  "visitor": { "id": "...", "visitor_code": "VIS-...", "full_name": "<name>", "company_name": null },
  "profile_id": "00000000-0000-0000-0000-000000000000",
  "model_version": "mock-v1",
  "embedding_version": "1",
  "consent_recorded": true,
  "duplicate_review": false
}

// DELETE /face/profiles/{id} data
{
  "id": "00000000-0000-0000-0000-000000000000",
  "visitor_id": "00000000-0000-0000-0000-000000000000",
  "model_version": "mock-v1",
  "embedding_version": "1",
  "is_active": false,
  "enrolled_at": "...",
  "updated_at": "...",
  "deleted_at": null
}
```

Business rules: exactly one face must be detected (`NO_FACE_DETECTED`,
`MULTIPLE_FACES_DETECTED`) and pass quality checks (`FACE_QUALITY_REJECTED`
with `details.issues`). A very similar face on another visitor returns
`409 FACE_DUPLICATE_DETECTED` with `details` containing
`matched_visitor_id`, `matched_visitor_code`, `matched_visitor_name`,
`similarity`, `review_required`. Enrolling again over an existing active
profile requires `replace_existing=true` (`409 FACE_PROFILE_EXISTS`), and
returns `409 FACE_PROFILE_CONFLICT` on concurrent races. When
`delete_biometrics=true`, `reason` must be at least 3 characters
(`422 REASON_REQUIRED`); deletion clears the stored embedding and sets
`deleted_at`. Image bytes are sniffed, so the declared content type must match
the actual file (`INVALID_IMAGE_FORMAT`, `IMAGE_TYPE_MISMATCH`); minimum
dimensions are 40x40 and max 25 MP.

### 7. Face Identification (1)

| Method | Path | Auth | Permission | Body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/face/identify` | Bearer or `X-Kiosk-Token` | `face:identify` (staff only) | multipart `image` | 200 |

```json
{
  "match_status": "MATCHED",
  "visitor": { "id": "...", "visitor_code": "VIS-...", "full_name": "<name>", "company_name": null },
  "confidence": 0.9123,
  "review_required": false,
  "active_visit_id": "00000000-0000-0000-0000-000000000000",
  "active_visit_status": "CHECKED_IN"
}
```

`match_status`: `MATCHED`, `UNKNOWN`, `REVIEW_REQUIRED`. `visitor` and
`confidence` are `null` when unknown. `active_visit_id` /
`active_visit_status` are present only when the matched visitor has an active
visit. `confidence` is a JSON number here. Only visitors with active
biometric consent and an active profile participate in matching. The image
must pass the same quality and liveness gates as enrollment.

### 8. Face Verification (1)

| Method | Path | Auth | Permission | Body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/face/verify` | Bearer or `X-Kiosk-Token` | `face:verify` (staff only) | multipart `visitor_id`, `image` | 200 |

```json
{ "matched": true, "confidence": 0.9123, "visitor_id": "00000000-0000-0000-0000-000000000000" }
```

Business rules: inactive visitor (`409 VISITOR_INACTIVE`), missing biometric
authorization (`409 BIOMETRIC_AUTHORIZATION_REQUIRED`), or no active profile
(`404 FACE_PROFILE_NOT_FOUND`) fail before image processing.

### 9. Liveness Detection (1)

| Method | Path | Auth | Permission | Body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/face/liveness` | Bearer or `X-Kiosk-Token` | `face:identify` (staff only) | multipart `image` | 200 |

```json
{ "passed": true, "score": 0.9876, "provider": "mock" }
```

This endpoint is a diagnostic check: it returns `200` with `passed: true` or
`passed: false` and does **not** raise on a failed liveness result. It only
fails with `422 FACE_QUALITY_REJECTED` (or image decode/validation errors) when
the image itself is unusable. By contrast, the enroll/identify/verify flows
enforce liveness internally and raise `422 LIVENESS_FAILED` when it fails.

### 10. Attendance Check-in (1)

| Method | Path | Auth | Permission | Body / header | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/attendance/check-in` | Bearer or `X-Kiosk-Token` | `attendance:write` (staff only) | `CheckInRequest`, optional `Idempotency-Key` | 201 |

```json
// CheckInRequest
{
  "visitor_id": "<uuid>",
  "kiosk_id": "<optional uuid>",
  "visit_id": "<optional uuid>",
  "purpose": "<optional ≤255>",
  "host_employee_id": "<optional uuid>",
  "method": "MANUAL",
  "confidence_score": 0.95
}

// data
{
  "attendance_id": "00000000-0000-0000-0000-000000000000",
  "visit_id": "00000000-0000-0000-0000-000000000000",
  "visitor": { "id": "...", "visitor_code": "VIS-...", "full_name": "<name>", "company_name": null },
  "event_type": "CHECK_IN",
  "event_timestamp": "...",
  "visit_status": "CHECKED_IN",
  "check_in_at": "...",
  "check_out_at": null,
  "kiosk_id": null
}
```

`method`: `FACE` or `MANUAL` (default `MANUAL`). `FACE` requires active
biometric consent (`403 BIOMETRIC_AUTHORIZATION_REQUIRED` otherwise).
`confidence_score` must be between 0 and 1 when provided. A kiosk token forces
`kiosk_id` to the authenticated kiosk and rejects mismatches (`403
KIOSK_MISMATCH`). When `visit_id` is omitted, the visitor's active `WAITING`
visit is used, or a new visit is created implicitly. Business errors:
`VISITOR_INACTIVE`, `VISIT_NOT_FOUND`, `VISIT_VISITOR_MISMATCH`,
`VISIT_NOT_ACTIVE`, `ALREADY_CHECKED_IN`, `ACTIVE_VISIT_EXISTS`,
`DUPLICATE_ATTENDANCE`. With an `Idempotency-Key`, retries with the identical
payload return the original `201` response; different payload returns `409
IDEMPOTENCY_KEY_REUSED`; the same key on check-out returns `409
IDEMPOTENCY_KEY_CONFLICT`.

### 11. Attendance Check-out (1)

| Method | Path | Auth | Permission | Body / header | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/attendance/check-out` | Bearer or `X-Kiosk-Token` | `attendance:write` (staff only) | `CheckOutRequest`, optional `Idempotency-Key` | 200 |

```json
// CheckOutRequest
{
  "visitor_id": "<uuid>",
  "kiosk_id": "<optional uuid>",
  "visit_id": "<optional uuid>",
  "method": "MANUAL",
  "confidence_score": 0.95
}
```

Response data has the same shape as check-in with `event_type: "CHECK_OUT"` and
`visit_status: "CHECKED_OUT"`. Business errors: `ALREADY_CHECKED_OUT`,
`NOT_CHECKED_IN`, `NO_ACTIVE_VISIT`, `VISIT_VISITOR_MISMATCH`,
`DUPLICATE_ATTENDANCE`. The same idempotency semantics as check-in apply
(scope is per-operation).

### 12. Attendance History (2) + Correction (1, admin module)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| GET | `/attendance` | Bearer | `attendance:read` | `page`, `page_size`, `visitor_id`, `event_type`, `date_from`, `date_to`, `kiosk_id` | 200 + meta |
| GET | `/attendance/{attendance_id}` | Bearer | `attendance:read` | path UUID | 200 |
| POST | `/admin/attendance/{attendance_id}/correct` | Bearer only | `attendance:correct` | `AttendanceCorrectionRequest` | 200 |

```json
// AttendanceCorrectionRequest
{
  "corrected_event_type": "CHECK_IN",
  "corrected_timestamp": "2026-11-11T03:00:00+00:00",
  "reason": "<required 3..255>"
}

// AttendanceLogOut (data)
{
  "id": "00000000-0000-0000-0000-000000000000",
  "visit_id": "00000000-0000-0000-0000-000000000000",
  "visitor_id": "00000000-0000-0000-0000-000000000000",
  "event_type": "CHECK_IN",
  "event_timestamp": "...",
  "kiosk_id": null,
  "confidence_score": "0.9500",
  "is_correction": false,
  "correction_of_id": null,
  "correction_reason": null,
  "created_at": "..."
}
```

`confidence_score` is serialized as a **string** in `AttendanceLogOut`
(`Decimal` in Pydantic JSON mode). Do not assume a number. Corrections are
append-only: a new row is stored with `is_correction: true` and
`correction_of_id`, and the visit's `check_in_at` / `check_out_at` is updated.
Corrections cannot be corrected (`409 INVALID_CORRECTION_TARGET`) and cannot
change the event type (`422 UNSUPPORTED_CORRECTION`). The endpoint is
staff-only; kiosk tokens are rejected with `403 FORBIDDEN`.

### 13. Dashboard and Statistics (1)

| Method | Path | Auth | Permission | Success |
| --- | --- | --- | --- | --- |
| GET | `/reports/dashboard` | Bearer | `report:read` | 200 |

```json
{
  "total_visitors": 0,
  "active_visitors": 0,
  "visitors_currently_inside": 0,
  "today_check_ins": 0,
  "today_check_outs": 0,
  "pending_visits": 0,
  "active_kiosks": 0,
  "generated_at": "...",
  "timezone": "Asia/Jakarta"
}
```

"Today" is computed in the configured business timezone (`Asia/Jakarta`);
correction rows are excluded from counts.

### 14. Reports and Export (4)

| Method | Path | Auth | Permission | Params | Success |
| --- | --- | --- | --- | --- | --- |
| GET | `/reports/attendance/daily` | Bearer | `report:read` | `date` (date, optional) | 200 |
| GET | `/reports/attendance/monthly` | Bearer | `report:read` | `year` 2000..2100, `month` 1..12 | 200 |
| GET | `/reports/visitors` | Bearer | `report:read` | `search` (≤150), `limit` 1..2000 (default 500) | 200 |
| GET | `/reports/attendance/export` | Bearer | `report:read` | `report_type` daily\|monthly\|visitors, `format` csv\|xlsx, `date_from`, `date_to`, `year`, `month` | 200 file |

```json
// DailyReportOut
{
  "date": "2026-11-11",
  "timezone": "Asia/Jakarta",
  "total_check_ins": 0,
  "total_check_outs": 0,
  "rows": [ { "hour": 0, "check_ins": 0, "check_outs": 0 } ]
}

// MonthlyReportOut
{
  "year": 2026,
  "month": 11,
  "timezone": "Asia/Jakarta",
  "total_check_ins": 0,
  "total_check_outs": 0,
  "rows": [ { "date": "2026-11-01", "check_ins": 0, "check_outs": 0 } ]
}

// VisitorReportOut
{
  "items": [
    { "visitor_id": "...", "visitor_code": "VIS-...", "full_name": "<name>", "company_name": null, "visit_count": 0, "last_visit_at": null }
  ],
  "total": 0
}
```

Current reporting behavior (verified in source and tests):

- Daily rows are grouped by local hour (`Asia/Jakarta`) and only include hours
  with activity; monthly rows are grouped by local date.
- The visitor report aggregates `visit_count` and `last_visit_at` per visitor
  via a grouped subquery joined back to `visitors`, sorted by visit count
  descending then name ascending, including visitors with zero visits. This
  query was rewritten for SQL Server `GROUP BY` compatibility (the previous
  version raised SQL Server error 8120; a dedicated SQL Server integration
  test `test_visitor_report_group_by_compatible_with_sqlserver` now covers it).
- `search` matches `full_name` or `visitor_code` (case-insensitive contains)
  and applies to both `items` and `total`.
- `total` is the number of matching visitors, `items` is capped by `limit`.
- Exports: `daily` covers `date_from`..`date_to` (default last 30 days ending
  today, local dates), `monthly` uses `year`/`month` (default current), and
  `visitors` exports the visitor report (limit 2000). CSV is UTF-8 with BOM;
  XLSX is a real workbook (openpyxl). Filenames embed the range and type.

Export returns raw file bytes (not the JSON envelope) with
`Content-Disposition: attachment; filename="..."` and media type `text/csv`
or the XLSX type. Use `responseType: "blob"` in the frontend.

### 15. Kiosk Management (4)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/kiosks` | Bearer | `kiosk:manage` | `KioskCreate` | 201 |
| GET | `/kiosks` | Bearer | `kiosk:read` | `page`, `page_size`, `is_active` | 200 + meta |
| GET | `/kiosks/{kiosk_id}` | Bearer | `kiosk:read` | path UUID | 200 |
| PATCH | `/kiosks/{kiosk_id}/status` | Bearer | `kiosk:manage` | `KioskStatusUpdate` | 200 |

```json
// KioskCreate
{ "kiosk_code": "<≤30>", "device_name": "<≤150>", "location": "<optional ≤150>" }

// KioskStatusUpdate
{ "is_active": true }

// KioskOut (data)
{
  "id": "00000000-0000-0000-0000-000000000000",
  "kiosk_code": "<code>",
  "device_name": "<name>",
  "location": null,
  "is_active": true,
  "last_seen_at": null,
  "created_at": "...",
  "updated_at": "..."
}

// POST /kiosks data additionally contains:
{ "device_token": "<returned once; store securely>" }
```

`device_token` is never returned again. There is no rotate/regenerate token
endpoint. Duplicate `kiosk_code` returns `409 KIOSK_CODE_EXISTS`. Only
`SUPER_ADMIN` holds `kiosk:manage`; other roles can list/read. `last_seen_at`
updates passively on kiosk-authenticated API calls (throttled to once per
minute).

### 16. User Management (3)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| GET | `/admin/users` | Bearer | `user:manage` | `page`, `page_size`, `role`, `is_active` | 200 + meta |
| POST | `/admin/users` | Bearer | `user:manage` | `UserCreate` | 201 |
| PATCH | `/admin/users/{user_id}` | Bearer | `user:manage` | `UserUpdate` | 200 |

```json
// UserCreate
{
  "username": "<3..50, [A-Za-z0-9_.-]+>",
  "email": "<email>",
  "password": "<12..255>",
  "full_name": "<1..150>",
  "role": "VIEWER"
}

// UserUpdate
{ "email": "<optional>", "full_name": "<optional>", "role": "VIEWER", "is_active": true, "password": "<optional 12..255>" }

// data is UserOut (same shape as /auth/me data)
```

`role` values: `SUPER_ADMIN`, `ADMIN`, `RECEPTIONIST`, `SECURITY`, `VIEWER`.
There is no delete-user endpoint; deactivate via `PATCH` with
`is_active: false`. Passwords must pass the strength rules (`422` with the
list of violations in `details`). Duplicate username/email return
`409 USERNAME_EXISTS` / `409 EMAIL_EXISTS`. Changing `password`, `role`, or
`is_active` revokes all the target user's sessions immediately.

### 17. Employee Management (5)

| Method | Path | Auth | Permission | Params / body | Success |
| --- | --- | --- | --- | --- | --- |
| POST | `/employees` | Bearer | `employee:write` | `EmployeeCreate` | 201 |
| GET | `/employees` | Bearer | `employee:read` | `page`, `page_size`, `search` (≤150), `is_active` | 200 + meta |
| GET | `/employees/{employee_id}` | Bearer | `employee:read` | path UUID | 200 |
| PUT | `/employees/{employee_id}` | Bearer | `employee:write` | `EmployeeUpdate` | 200 |
| DELETE | `/employees/{employee_id}` | Bearer | `employee:write` | path UUID | 200 (soft deactivate) |

```json
// EmployeeCreate
{ "employee_code": "<1..30>", "full_name": "<1..150>", "department": "<optional ≤100>", "email": "<optional email>", "phone_number": "<optional ≤30>" }

// EmployeeUpdate
{ "full_name": "<optional>", "department": "<optional>", "email": "<optional>", "phone_number": "<optional>", "is_active": true }

// EmployeeOut (data)
{
  "id": "...", "employee_code": "...", "full_name": "...", "department": null,
  "email": null, "phone_number": null, "is_active": true,
  "created_at": "...", "updated_at": "..."
}
```

Business rules: unique `employee_code` (`409 EMPLOYEE_CODE_EXISTS`) and email
(`409 EMPLOYEE_EMAIL_EXISTS`); emails are lowercased. Note that
`employee:write` is required for `DELETE` (deactivation), unlike visitors
which use `visitor:delete`.

### 18. Audit Logs (1)

| Method | Path | Auth | Permission | Params | Success |
| --- | --- | --- | --- | --- | --- |
| GET | `/admin/audit-logs` | Bearer | `audit:read` | `page`, `page_size`, `user_id`, `action` (≤100), `entity_type` (≤100) | 200 + meta |

```json
// AuditLogOut (data)
{
  "id": "...", "user_id": null, "action": "LOGIN_SUCCESS", "entity_type": "user",
  "entity_id": "...", "description": "...", "ip_address": "127.0.0.1", "created_at": "..."
}
```

Recorded actions include `LOGIN_SUCCESS`, `LOGIN_FAILED`, `TOKEN_REFRESHED`,
`REFRESH_TOKEN_REUSE_DETECTED`, `LOGOUT`, `USER_CREATED`, `USER_UPDATED`,
`VISITOR_CREATED`, `VISITOR_UPDATED`, `VISITOR_DEACTIVATED`,
`BIOMETRIC_CONSENT_WITHDRAWN`, `BIOMETRIC_DATA_DELETED`, `VISIT_CREATED`,
`VISIT_UPDATED`, `VISIT_CANCELLED`, `FACE_ENROLLED`, `FACE_IDENTIFIED`,
`FACE_VERIFIED`, `FACE_PROFILE_DELETED`, `FACE_PROFILE_DEACTIVATED`,
`LIVENESS_TESTED`, `ATTENDANCE_CHECK_IN`, `ATTENDANCE_CHECK_OUT`,
`ATTENDANCE_CORRECTED`, `EMPLOYEE_CREATED`, `EMPLOYEE_UPDATED`,
`EMPLOYEE_DEACTIVATED`, `KIOSK_CREATED`, `KIOSK_STATUS_CHANGED`. There is no
audit export endpoint.

## Verified connectivity (live, 2026-11-11)

| Check | Result |
| --- | --- |
| `GET /health` | 200, `status: ok` |
| `GET /ready` | 200, database + mock face + mock liveness ready |
| `GET /docs` | 200 |
| `GET /openapi.json` | 200, OpenAPI 3.1.0, 47 operations / 37 paths |
| Unauthenticated staff reads (`/api/v1/visitors`) | 401 `UNAUTHORIZED` |
| Unknown route | 404 `HTTP_404` |
| Wrong method (`DELETE /health`) | 405 `HTTP_405` |
| Invalid login body | 422 `VALIDATION_ERROR` with `details[]` |
| CORS preflight from `http://localhost:8080` | 200 with expected allow headers/methods, credentials allowed |
| Rate limit headers | `Retry-After` on `429` |

Protected operations were **not** executed against real data: no test
credentials are known and mutations are out of scope for this task. Only
unauthenticated behavior, safe read-only probes, and source code inspection
were used.

## Frontend integration notes

1. Always unwrap the envelope. On `success: false`, branch on `error_code`,
   not on the message text.
2. Keep access tokens in memory; refresh proactively before `expires_in`.
   Never log tokens or put them in URLs.
3. A single 401 does not always mean "log in": `INVALID_TOKEN`,
   `TOKEN_REVOKED`, `ACCOUNT_DISABLED`, `REFRESH_TOKEN_EXPIRED`, and
   `REFRESH_TOKEN_REUSED` require different handling. Attempt one refresh,
   then force logout on failure. `REFRESH_TOKEN_REUSED` should immediately
   force logout (all sessions were revoked server-side).
4. Send `Idempotency-Key` on check-in/check-out retries. Replaying the same key
   with a different payload returns `409 IDEMPOTENCY_KEY_REUSED`; using the
   same key across check-in and check-out returns `409
   IDEMPOTENCY_KEY_CONFLICT`. Keys are retained for 24 hours.
5. `DELETE /visitors/{id}/biometric` requires a JSON body. Ensure the HTTP
   client actually sends it; some proxies drop DELETE bodies.
6. `confidence_score` is a **string** in attendance history
   (`AttendanceLogOut`) and is not included in the check-in/check-out response
   data. Face result `confidence` / `score` values are JSON numbers. Normalize
   before formatting.
7. Uploads are limited to 5 MB and JPEG/PNG/WebP. Reject larger files client
   side before upload (`413 FILE_TOO_LARGE`). The declared multipart content
   type must match the actual image bytes.
8. All responses set `Cache-Control: no-store`; do not cache sensitive data.
9. Kiosk UI must use `X-Kiosk-Token` and must not expose staff JWTs. Staff UI
   must never send kiosk tokens. Do not send both headers on the same request.
10. Report export is a binary download, not JSON. Use `responseType: "blob"`
    and read the filename from `Content-Disposition`.
11. Business dates are evaluated in `Asia/Jakarta`; display timezone
    explicitly. Timestamps in payloads are UTC.
12. There is no WebSocket/SSE endpoint. Use polling (for example dashboard and
    attendance lists) with a reasonable interval and respect rate limits
    (`429` includes `Retry-After`).
13. `GET /ready` returning 503 still has a parseable body; use `data.ready`
    and `data.checks` for diagnostics.
