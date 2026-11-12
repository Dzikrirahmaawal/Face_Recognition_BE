# Frontend Integration Plan

Companion to `docs/frontend-api-reference.md` and `docs/frontend-api-types.ts`.
Scope: what a Vue.js (or any SPA) frontend can consume today, in what order,
and what is missing. No backend or database changes are proposed here.

Regenerated on 2026-11-11 from the current backend source and live OpenAPI
(47 operations / 37 paths). Supersedes earlier revisions.

## Readiness summary

- Backend is live and healthy: `/health` 200, `/ready` 200 (SQL Server + mock
  face + mock liveness in the current development configuration).
- OpenAPI 3.1.0 exposes **47 operations across 37 paths**.
- All staff data endpoints require a JWT bearer access token.
- Kiosk flows require an `X-Kiosk-Token` obtained once at kiosk creation.
- Protected calls return `401 UNAUTHORIZED` without credentials. This task did
  not use any real credentials, so write flows were not exercised live; they
  were verified from source and the automated test suite.
- The visitor report SQL Server `GROUP BY` bug is already fixed in the current
  source (`app/services/report_service.py`) and covered by a SQL Server
  integration test.

## Authentication architecture for the frontend

| Concern | Decision |
| --- | --- |
| Staff login | `POST /api/v1/auth/login`; `username` accepts username or email |
| Token storage | Access token in memory; refresh token in the safest available store (the API returns tokens in the JSON body; it does not set cookies) |
| Attach auth | Axios/fetch interceptor adds `Authorization: Bearer <access_token>` |
| Refresh | On `401` with `INVALID_TOKEN`/expired, call `POST /auth/refresh` once, then retry the original request |
| Force logout | On refresh failure, `TOKEN_REVOKED`, `ACCOUNT_DISABLED`, `REFRESH_TOKEN_EXPIRED`, or `REFRESH_TOKEN_REUSED`, clear state and route to login |
| Logout | `POST /auth/logout` with the current access token; send `refresh_token` and `all_devices` as needed |
| Session bootstrap | `GET /auth/me` after refresh/page reload |
| Role gating | Derive UI visibility from `user.role`; the server still enforces permissions |
| Kiosk auth | Separate client/route; `X-Kiosk-Token` only, never staff JWTs |
| Idempotency | Send `Idempotency-Key` on attendance writes; reuse only for the identical payload |

Because tokens are returned in JSON (no `Set-Cookie`), the frontend must handle
XSS risk explicitly: avoid `localStorage` where possible, never log tokens, and
apply a strict CSP on the frontend host. Note the backend already sends
`Cache-Control: no-store` on API responses.

## Endpoint selection by frontend area

### Dashboard and statistics

| Need | Endpoint | Auth |
| --- | --- | --- |
| KPI cards | `GET /api/v1/reports/dashboard` | Staff JWT, `report:read` |
| Daily trend | `GET /api/v1/reports/attendance/daily?date=YYYY-MM-DD` | Staff JWT, `report:read` |
| Monthly trend | `GET /api/v1/reports/attendance/monthly?year=&month=` | Staff JWT, `report:read` |
| Who is currently inside | `GET /api/v1/visits?status=CHECKED_IN` | Staff JWT, `visit:read` |
| Pending/waiting visitors | `GET /api/v1/visits?status=WAITING` | Staff JWT, `visit:read` |
| Recent attendance | `GET /api/v1/attendance?date_from=&date_to=` | Staff JWT, `attendance:read` |

`reports/dashboard` already returns `visitors_currently_inside`,
`today_check_ins`, `today_check_outs`, `pending_visits`, and `active_kiosks`, so
the dashboard can be built from one call plus optional drill-downs. Counts use
the `Asia/Jakarta` business day and exclude correction rows.

### Visitor management

| Need | Endpoint | Auth |
| --- | --- | --- |
| Visitor list + search/filter | `GET /api/v1/visitors?page=&page_size=&search=&is_active=` | `visitor:read` |
| Visitor detail | `GET /api/v1/visitors/{visitor_id}` | `visitor:read` |
| Register visitor | `POST /api/v1/visitors` | `visitor:write` |
| Edit visitor | `PUT /api/v1/visitors/{visitor_id}` | `visitor:write` |
| Deactivate visitor | `DELETE /api/v1/visitors/{visitor_id}` | `visitor:delete` |
| Face enrollment status | `has_active_face_profile` in `VisitorOut` | `visitor:read` |
| Consent history | `GET /api/v1/visitors/{visitor_id}/consents` | `privacy:manage` |
| Withdraw biometric consent | `POST /api/v1/visitors/{visitor_id}/biometric/withdraw` | `privacy:manage` |
| Erase biometric data | `DELETE /api/v1/visitors/{visitor_id}/biometric` | `privacy:manage` |
| Host lookup for visit form | `GET /api/v1/employees?is_active=true` | `employee:read` |
| Create visit from visitor | `POST /api/v1/visits` | `visit:write` |

Recommended UX: the visitor detail page combines `VisitorOut`, consents, and
the visitor's visits (`GET /visits?visitor_id=`). Deactivation is soft; label it
"Deactivate", not "Delete". Deactivation also deactivates active face profiles,
so face flows stop matching immediately.

### Visit management

| Need | Endpoint | Auth |
| --- | --- | --- |
| List/filter visits | `GET /api/v1/visits?status=&visitor_id=&date_from=&date_to=&search=` | `visit:read` |
| Visit detail | `GET /api/v1/visits/{visit_id}` | `visit:read` |
| Pre-register visit | `POST /api/v1/visits` | `visit:write` |
| Edit open visit | `PUT /api/v1/visits/{visit_id}` | `visit:write` |
| Cancel waiting visit | `POST /api/v1/visits/{visit_id}/cancel` | `visit:write` |

Visit state machine (current implementation):

- `WAITING -> CHECKED_IN -> CHECKED_OUT`.
- Only `WAITING` visits can be cancelled to `CANCELLED`.
- Cancelling a `CHECKED_IN` visit returns `409 VISIT_CHECKOUT_REQUIRED` — the
  UI must record check-out first, then cancel is no longer applicable.
- Cancelling a `CHECKED_OUT` visit returns `409 VISIT_ALREADY_CLOSED`;
  cancelling twice returns `409 VISIT_ALREADY_CANCELLED`.
- Closed (`CHECKED_OUT`/`CANCELLED`) visits cannot be edited
  (`409 VISIT_NOT_EDITABLE`).
- A visitor may have at most one active (`WAITING` or `CHECKED_IN`) visit
  (`409 ACTIVE_VISIT_EXISTS`).

### Attendance check-in / check-out

| Need | Endpoint | Auth |
| --- | --- | --- |
| Manual check-in (reception) | `POST /api/v1/attendance/check-in` with `method: "MANUAL"` | Staff JWT, `attendance:write` |
| Face check-in | `POST /api/v1/attendance/check-in` with `method: "FACE"` | Staff JWT or kiosk token |
| Manual check-out | `POST /api/v1/attendance/check-out` | Staff JWT, `attendance:write` |
| Face check-out | `POST /api/v1/attendance/check-out` with `method: "FACE"` | Staff JWT or kiosk token |

Always send `Idempotency-Key` on retries. Reuse the same key only for the exact
same payload and only within the same operation. Handle `ALREADY_CHECKED_IN`,
`ALREADY_CHECKED_OUT`, `NOT_CHECKED_IN`, `NO_ACTIVE_VISIT`,
`BIOMETRIC_AUTHORIZATION_REQUIRED`, `KIOSK_MISMATCH`, `ACTIVE_VISIT_EXISTS`,
`DUPLICATE_ATTENDANCE`, `IDEMPOTENCY_KEY_REUSED`, and
`IDEMPOTENCY_KEY_CONFLICT` with specific UI messages. A check-in can implicitly
create a visit if the visitor has no active waiting visit.

### Attendance history

| Need | Endpoint | Auth |
| --- | --- | --- |
| Paginated history | `GET /api/v1/attendance?page=&page_size=&visitor_id=&event_type=&date_from=&date_to=&kiosk_id=` | `attendance:read` |
| Detail | `GET /api/v1/attendance/{attendance_id}` | `attendance:read` |
| Correct timestamp | `POST /api/v1/admin/attendance/{attendance_id}/correct` | `attendance:correct` (staff only) |

Corrections are append-only records (`is_correction: true`, `correction_of_id`)
and cannot change the event type (`422 UNSUPPORTED_CORRECTION`) or correct a
correction (`409 INVALID_CORRECTION_TARGET`). Show both original and correction
rows. `confidence_score` is a string in this list view.

### Face recognition kiosk workflow

| Step | Endpoint | Auth |
| --- | --- | --- |
| Liveness pre-check | `POST /api/v1/face/liveness` | Kiosk token or staff JWT (`face:identify`) |
| Identify visitor | `POST /api/v1/face/identify` | Kiosk token or staff JWT (`face:identify`) |
| Verify a known visitor | `POST /api/v1/face/verify` | Kiosk token or staff JWT (`face:verify`) |
| Enroll a new face | `POST /api/v1/face/enroll` | Kiosk token or staff JWT (`face:enroll`) |
| Check in / out | `POST /api/v1/attendance/check-in` / `check-out` | Kiosk token or staff JWT |

Recommended kiosk flow: capture image -> `identify` (which internally enforces
liveness and quality) -> if `MATCHED` and no active visit, `check-in`; if the
visitor already has an active `CHECKED_IN` visit, `check-out`. If
`REVIEW_REQUIRED`, route to a staff review queue. Enrollment requires
`consent_granted=true`. The kiosk client must send `X-Kiosk-Token` and never a
staff JWT.

### Kiosk management

| Need | Endpoint | Auth |
| --- | --- | --- |
| List kiosks | `GET /api/v1/kiosks?page=&page_size=&is_active=` | `kiosk:read` |
| Kiosk detail | `GET /api/v1/kiosks/{kiosk_id}` | `kiosk:read` |
| Register kiosk | `POST /api/v1/kiosks` | `kiosk:manage` |
| Enable/disable kiosk | `PATCH /api/v1/kiosks/{kiosk_id}/status` | `kiosk:manage` |

The creation response contains `device_token` once. Build a one-time
"provisioning" screen that shows the token and requires the operator to copy it
to the kiosk before dismissing. Never re-fetch or display it later. There is no
token rotation endpoint; a lost token currently requires disabling the kiosk.
`last_seen_at` updates passively on kiosk calls.

### Reports

| Need | Endpoint | Auth |
| --- | --- | --- |
| Daily attendance report | `GET /api/v1/reports/attendance/daily` | `report:read` |
| Monthly attendance report | `GET /api/v1/reports/attendance/monthly` | `report:read` |
| Visitor activity report | `GET /api/v1/reports/visitors?search=&limit=` | `report:read` |
| CSV/XLSX export | `GET /api/v1/reports/attendance/export` | `report:read` |

Export is a blob download; use `responseType: "blob"` and read
`Content-Disposition` for the filename. Daily exports default to the last 30
local days; monthly exports default to the current month; visitor exports cap
at 2000 rows. CSV is UTF-8 with BOM (Excel-friendly).

### Administration

| Area | Endpoints | Auth |
| --- | --- | --- |
| Users | `GET/POST /api/v1/admin/users`, `PATCH /api/v1/admin/users/{user_id}` | `user:manage` |
| Audit logs | `GET /api/v1/admin/audit-logs` | `audit:read` |
| Employees | `/api/v1/employees` CRUD | `employee:read` / `employee:write` |
| Consent/privacy | visitor consent endpoints | `privacy:manage` |
| Attendance correction | `POST /api/v1/admin/attendance/{id}/correct` | `attendance:correct` |

Only `SUPER_ADMIN` holds `user:manage` and `kiosk:manage`. Changing a user's
password, role, or active state revokes their sessions immediately.

## Kiosk vs admin (staff) token usage

| Capability | Staff JWT | `X-Kiosk-Token` |
| --- | --- | --- |
| Face enroll | yes (`face:enroll`) | yes |
| Face identify | yes (`face:identify`) | yes |
| Face verify | yes (`face:verify`) | yes |
| Liveness | yes (`face:identify`) | yes |
| Check-in / check-out | yes (`attendance:write`) | yes |
| Attendance correction | yes (`attendance:correct`) | no |
| Delete face profile | yes (`face:delete`) | no |
| Visitors / visits / reports / kiosks / admin | yes (role-dependent) | no |

Implement two separate API clients:

- **Staff client**: bearer interceptor, refresh, role-aware navigation.
- **Kiosk client**: static kiosk token header, camera capture, retry with
  idempotency keys, no login UI.

Never send both `Authorization` and `X-Kiosk-Token` on the same request: the
backend treats the kiosk header as authoritative.

## Data dependencies between modules

- Create a visitor before a visit, face enrollment, or attendance.
- Create an employee before assigning a visit host.
- Create a kiosk and deliver its `device_token` before kiosk check-in/out.
- Enroll a face (with consent) before face identification/verification will
  match that visitor.
- A `CHECK_IN` requires an active (non-cancelled, non-checked-out) visit or
  creates one automatically.
- A `CHECK_OUT` requires a `CHECKED_IN` visit.
- Biometric consent withdrawal/deletion deactivates active face profiles, so
  face flows stop matching immediately.
- Reports and the dashboard depend on visits and attendance logs existing.

## Recommended consumption order

1. **Foundation**: `/health`, `/ready`, login/refresh/logout/me, envelope and
   error handling, 401 refresh interceptor, role gating.
2. **Read-only staff shell**: dashboard (`/reports/dashboard`), visitors list,
   visits list, attendance list. Safe to ship first; no writes.
3. **Visitor and visit workflows**: create/edit/deactivate visitor, create/edit
   visit, cancel waiting visit, employee lookup.
4. **Attendance workflows**: manual check-in/out with idempotency keys,
   attendance detail, correction (admin only).
5. **Reports**: daily/monthly/visitors views, blob export.
6. **Administration**: users, employees, kiosks (including one-time token
   provisioning), audit logs.
7. **Privacy/consent**: per-visitor consent history, withdraw, biometric erase.
8. **Kiosk client**: face capture UI, liveness, identify/verify, enroll,
   check-in/out with kiosk token and retries.

## Suggested polling

| View | Suggested interval | Endpoint |
| --- | --- | --- |
| Dashboard counters | 15–30 s | `/reports/dashboard` |
| Currently inside | 15–30 s | `/visits?status=CHECKED_IN` |
| Attendance feed | 10–20 s | `/attendance?date_from=...` |
| Kiosk status | 30–60 s | `/kiosks` |

Stay below the global rate limit (300 requests / 60 s per IP + path; login is
10 / 60 s). On `429`, honor the `Retry-After` header. Pause polling when the tab
is hidden.

## Current backend limitations and gaps

These are not present in the backend today. Do not build UI that assumes them.

1. **Seed/admin bootstrap in UI** — no public signup or first-admin endpoint.
   Provision the first SUPER_ADMIN out of band (`scripts/create_superadmin.py`).
2. **Consent grant endpoint** — consent is only recorded as part of
   `POST /face/enroll`. There is no standalone "record privacy notice" call.
3. **Consent history pagination/filtering** — `GET /visitors/{id}/consents`
   returns all records with no pagination.
4. **Face profile list/detail by visitor** — only `has_active_face_profile` is
   exposed; the only profile endpoint is deletion.
5. **Kiosk token rotation** — no rotate/regenerate/revoke-token endpoint. A lost
   token currently requires disabling the kiosk.
6. **User deletion** — only deactivation via `PATCH /admin/users/{id}`.
7. **Self-service profile/password change** — no `/auth/me` update or
   change-password endpoint; admins use `PATCH /admin/users/{id}`.
8. **Visit check-in/check-out convenience routes** — check-in/out live under
   `/attendance`; there are no `/visits/{id}/check-in` routes.
9. **Cancel a checked-in visit** — intentionally unsupported
   (`VISIT_CHECKOUT_REQUIRED`); the frontend must check out first.
10. **"Currently inside" dedicated endpoint** — use
    `GET /visits?status=CHECKED_IN` or dashboard counters.
11. **Real-time updates** — no WebSocket/SSE; polling only.
12. **Visitor photo/avatar** — no image URL or thumbnail field; embeddings are
    never exposed.
13. **Bulk visitor import/export** — only report export exists.
14. **Audit log export** — not available.
15. **System settings / policy management** — no endpoint for thresholds,
    retention, or consent policy text.
16. **Notifications** — no email/SMS/notification endpoints.
17. **Report filters by kiosk/employee/department** — reports accept date/year/
    month/search/limit only.
18. **Dashboard time range parameter** — the dashboard is fixed to "today".
19. **Kiosk heartbeat endpoint** — `last_seen_at` is updated implicitly on
    authenticated kiosk calls; there is no explicit heartbeat.
20. **Attendance correction of event type** — append-only timestamp corrections
    only (`UNSUPPORTED_CORRECTION`).

## Verified vs unverified in this task

- Verified live: `/health`, `/ready`, `/openapi.json` (47 operations / 37
  paths), `/docs`, CORS preflight, 401/404/405/422 envelopes.
- Verified from source and tests: all endpoint contracts, RBAC, error codes,
  reporting behavior, and the SQL Server `visitor_report` fix.
- Not verified live: authenticated reads/writes and any mutation, because no
  credentials were used and destructive operations are out of scope.
