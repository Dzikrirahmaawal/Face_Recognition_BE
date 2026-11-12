/**
 * TypeScript types derived from the current backend Pydantic schemas and the
 * live OpenAPI document (`GET /openapi.json`, OpenAPI 3.1.0) on 2026-11-11.
 *
 * Conventions:
 * - UUIDs are strings.
 * - Timestamps are ISO-8601 UTC strings (`Z` / `+00:00`).
 * - Report `date` values are `YYYY-MM-DD` strings; business dates use the
 *   configured timezone (`Asia/Jakarta`).
 * - JSON field names are snake_case, matching the API exactly.
 * - `Decimal` fields serialized through Pydantic `model_dump(mode="json")`
 *   (AttendanceLogOut.confidence_score) arrive as strings; Decimal values sent
 *   through FastAPI's jsonable_encoder (face result confidence/score) arrive
 *   as numbers. Check-in/check-out response data does not include a confidence
 *   score. This difference is intentional and reflected below.
 * - `undefined`/`?` marks fields that may be omitted from a request. `null`
 *   marks fields the API can return as JSON null.
 * - Do not add fields that are not returned by the API.
 *
 * This file is self-contained and passes `tsc --strict --noEmit`.
 */

export const API_PREFIX = "/api/v1" as const;

/* -------------------------------------------------------------------------- */
/* Enums                                                                      */
/* -------------------------------------------------------------------------- */

export type UserRole =
  | "SUPER_ADMIN"
  | "ADMIN"
  | "RECEPTIONIST"
  | "SECURITY"
  | "VIEWER";

export type VisitStatus = "WAITING" | "CHECKED_IN" | "CHECKED_OUT" | "CANCELLED";

export type AttendanceEventType = "CHECK_IN" | "CHECK_OUT";

export type AttendanceMethod = "FACE" | "MANUAL";

export type MatchStatus = "MATCHED" | "UNKNOWN" | "REVIEW_REQUIRED";

export type ConsentType = "BIOMETRIC_PROCESSING" | "PRIVACY_NOTICE";

export type ConsentStatus = "GRANTED" | "WITHDRAWN";

export type ReportType = "daily" | "monthly" | "visitors";

export type ReportFormat = "csv" | "xlsx";

/**
 * Error codes currently emitted by the backend. Grouped by the HTTP status the
 * backend uses; some codes can appear with more than one status (noted).
 */
export type ApiErrorCode =
  // 400
  | "BAD_REQUEST"
  // 401
  | "UNAUTHORIZED"
  | "INVALID_CREDENTIALS"
  | "INVALID_TOKEN"
  | "INVALID_REFRESH_TOKEN"
  | "REFRESH_TOKEN_EXPIRED"
  | "REFRESH_TOKEN_REUSED"
  | "TOKEN_REVOKED"
  | "ACCOUNT_DISABLED"
  | "INVALID_KIOSK_TOKEN"
  | "KIOSK_DISABLED"
  // 403
  | "FORBIDDEN"
  | "KIOSK_MISMATCH"
  | "BIOMETRIC_AUTHORIZATION_REQUIRED" // 403 on attendance, 409 on face verify
  // 404
  | "NOT_FOUND"
  | "VISITOR_NOT_FOUND"
  | "VISIT_NOT_FOUND"
  | "ATTENDANCE_NOT_FOUND"
  | "EMPLOYEE_NOT_FOUND"
  | "HOST_EMPLOYEE_NOT_FOUND"
  | "KIOSK_NOT_FOUND"
  | "USER_NOT_FOUND"
  | "FACE_PROFILE_NOT_FOUND"
  // 409
  | "CONFLICT"
  | "VISITOR_INACTIVE"
  | "VISITOR_EXISTS"
  | "VISITOR_CONFLICT"
  | "VISITOR_CODE_EXHAUSTED"
  | "VISIT_VISITOR_MISMATCH"
  | "VISIT_NOT_ACTIVE"
  | "VISIT_NOT_EDITABLE"
  | "VISIT_ALREADY_CANCELLED"
  | "VISIT_ALREADY_CLOSED"
  | "VISIT_CHECKOUT_REQUIRED"
  | "ALREADY_CHECKED_IN"
  | "ALREADY_CHECKED_OUT"
  | "NOT_CHECKED_IN"
  | "NO_ACTIVE_VISIT"
  | "ACTIVE_VISIT_EXISTS"
  | "DUPLICATE_ATTENDANCE"
  | "INVALID_CORRECTION_TARGET"
  | "HOST_EMPLOYEE_INACTIVE"
  | "EMPLOYEE_CODE_EXISTS"
  | "EMPLOYEE_EMAIL_EXISTS"
  | "EMPLOYEE_CONFLICT"
  | "KIOSK_CODE_EXISTS"
  | "KIOSK_CONFLICT"
  | "KIOSK_INACTIVE"
  | "USERNAME_EXISTS"
  | "EMAIL_EXISTS"
  | "FACE_PROFILE_EXISTS"
  | "FACE_PROFILE_CONFLICT"
  | "FACE_DUPLICATE_DETECTED"
  | "IDEMPOTENCY_KEY_CONFLICT"
  | "IDEMPOTENCY_KEY_REUSED"
  // 413
  | "FILE_TOO_LARGE"
  // 422
  | "VALIDATION_ERROR"
  | "CONSENT_REQUIRED"
  | "VISITOR_NAME_REQUIRED"
  | "REASON_REQUIRED"
  | "FACE_QUALITY_REJECTED"
  | "NO_FACE_DETECTED"
  | "MULTIPLE_FACES_DETECTED"
  | "EMPTY_IMAGE"
  | "INVALID_IMAGE"
  | "INVALID_IMAGE_FORMAT"
  | "IMAGE_TOO_SMALL"
  | "IMAGE_DIMENSIONS_TOO_LARGE"
  | "IMAGE_TYPE_MISMATCH"
  | "LIVENESS_FAILED"
  | "UNSUPPORTED_CORRECTION"
  // 429
  | "RATE_LIMITED"
  // 500
  | "DATABASE_ERROR"
  | "INTERNAL_ERROR"
  // 503
  | "FACE_PROVIDER_UNAVAILABLE"
  // Framework-generated for unknown routes / methods
  | "HTTP_404"
  | "HTTP_405";

/* -------------------------------------------------------------------------- */
/* Envelope                                                                   */
/* -------------------------------------------------------------------------- */

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ApiSuccess<T> {
  success: true;
  message: string;
  data: T;
  meta: PaginationMeta | null;
}

export interface ApiValidationDetail {
  location: string;
  message: string;
  type: string;
}

export interface ApiError {
  success: false;
  message: string;
  error_code: ApiErrorCode;
  details: unknown;
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export interface PaginatedSuccess<T> {
  success: true;
  message: string;
  data: T[];
  meta: PaginationMeta;
}

export type PaginatedResponse<T> = PaginatedSuccess<T> | ApiError;

/* -------------------------------------------------------------------------- */
/* Authentication                                                             */
/* -------------------------------------------------------------------------- */

export interface LoginRequest {
  /** Accepts either the username or the email address. */
  username: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface LogoutRequest {
  refresh_token?: string | null;
  all_devices?: boolean;
}

export interface UserOut {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  /** Access-token lifetime in seconds (default 900). */
  expires_in: number;
}

export interface LoginData {
  user: UserOut;
  tokens: TokenPair;
}

export type LoginResponse = ApiSuccess<LoginData>;

/* -------------------------------------------------------------------------- */
/* Health                                                                     */
/* -------------------------------------------------------------------------- */

export interface HealthData {
  status: string;
  app: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface ReadyDatabaseCheck {
  ok: boolean;
  error?: string;
}

export interface ReadyFaceProviderCheck {
  ok: boolean;
  name?: string;
  model_version?: string;
  error?: string;
}

export interface ReadyLivenessProviderCheck {
  ok: boolean;
  name?: string;
  error?: string;
}

export interface ReadyChecks {
  database: ReadyDatabaseCheck;
  face_provider: ReadyFaceProviderCheck;
  liveness_provider: ReadyLivenessProviderCheck;
}

export interface ReadyData {
  ready: boolean;
  checks: ReadyChecks;
  timestamp: string;
}

/** `/ready` returns 503 with this body when `ready` is false. */
export type ReadyResponse = ApiSuccess<ReadyData>;

/* -------------------------------------------------------------------------- */
/* Visitors                                                                   */
/* -------------------------------------------------------------------------- */

export interface VisitorCreate {
  full_name: string;
  identity_number?: string | null;
  company_name?: string | null;
  phone_number?: string | null;
  email?: string | null;
}

export interface VisitorUpdate {
  full_name?: string | null;
  identity_number?: string | null;
  company_name?: string | null;
  phone_number?: string | null;
  email?: string | null;
  is_active?: boolean | null;
}

export interface VisitorSummary {
  id: string;
  visitor_code: string;
  full_name: string;
  company_name: string | null;
}

export interface VisitorOut {
  id: string;
  visitor_code: string;
  full_name: string;
  identity_number: string | null;
  company_name: string | null;
  phone_number: string | null;
  email: string | null;
  is_active: boolean;
  has_active_face_profile: boolean;
  created_at: string;
  updated_at: string;
}

export interface VisitorListQuery {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
}

export interface FaceProfileOut {
  id: string;
  visitor_id: string;
  model_version: string;
  embedding_version: string;
  is_active: boolean;
  enrolled_at: string;
  updated_at: string;
  deleted_at: string | null;
}

/* -------------------------------------------------------------------------- */
/* Consent / privacy                                                          */
/* -------------------------------------------------------------------------- */

export interface ConsentWithdrawRequest {
  reason?: string | null;
  policy_version?: string | null;
}

export interface BiometricDeleteRequest {
  reason: string;
  delete_face_profiles?: boolean;
}

export interface ConsentRecordOut {
  id: string;
  consent_type: ConsentType;
  policy_version: string;
  consent_status: ConsentStatus;
  consented_at: string | null;
  withdrawn_at: string | null;
  recorded_by: string | null;
  created_at: string;
}

/* -------------------------------------------------------------------------- */
/* Visits                                                                     */
/* -------------------------------------------------------------------------- */

export interface VisitCreate {
  visitor_id: string;
  purpose?: string | null;
  host_employee_id?: string | null;
}

export interface VisitUpdate {
  purpose?: string | null;
  host_employee_id?: string | null;
}

export interface VisitCancelRequest {
  reason?: string | null;
}

export interface VisitOut {
  id: string;
  visitor_id: string;
  visitor: VisitorSummary | null;
  purpose: string | null;
  host_employee_id: string | null;
  visit_status: VisitStatus;
  check_in_at: string | null;
  check_out_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VisitListQuery {
  page?: number;
  page_size?: number;
  visitor_id?: string;
  status?: VisitStatus;
  date_from?: string;
  date_to?: string;
  search?: string;
}

/* -------------------------------------------------------------------------- */
/* Employees                                                                  */
/* -------------------------------------------------------------------------- */

export interface EmployeeCreate {
  employee_code: string;
  full_name: string;
  department?: string | null;
  email?: string | null;
  phone_number?: string | null;
}

export interface EmployeeUpdate {
  full_name?: string | null;
  department?: string | null;
  email?: string | null;
  phone_number?: string | null;
  is_active?: boolean | null;
}

export interface EmployeeOut {
  id: string;
  employee_code: string;
  full_name: string;
  department: string | null;
  email: string | null;
  phone_number: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmployeeListQuery {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
}

/* -------------------------------------------------------------------------- */
/* Kiosks                                                                     */
/* -------------------------------------------------------------------------- */

export interface KioskCreate {
  kiosk_code: string;
  device_name: string;
  location?: string | null;
}

export interface KioskStatusUpdate {
  is_active: boolean;
}

export interface KioskOut {
  id: string;
  kiosk_code: string;
  device_name: string;
  location: string | null;
  is_active: boolean;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Returned only once, from POST /kiosks. Store securely on the kiosk. */
export interface KioskCreated extends KioskOut {
  device_token: string;
}

export interface KioskListQuery {
  page?: number;
  page_size?: number;
  is_active?: boolean;
}

/* -------------------------------------------------------------------------- */
/* Attendance                                                                 */
/* -------------------------------------------------------------------------- */

export interface CheckInRequest {
  visitor_id: string;
  kiosk_id?: string | null;
  visit_id?: string | null;
  purpose?: string | null;
  host_employee_id?: string | null;
  method?: AttendanceMethod;
  /** Decimal between 0 and 1; accepted as a number or numeric string. */
  confidence_score?: number | string | null;
}

export interface CheckOutRequest {
  visitor_id: string;
  kiosk_id?: string | null;
  visit_id?: string | null;
  method?: AttendanceMethod;
  /** Decimal between 0 and 1; accepted as a number or numeric string. */
  confidence_score?: number | string | null;
}

/** Check-in / check-out response data (no confidence score included). */
export interface AttendanceActionData {
  attendance_id: string;
  visit_id: string;
  visitor: VisitorSummary;
  event_type: AttendanceEventType;
  event_timestamp: string;
  visit_status: VisitStatus;
  check_in_at: string | null;
  check_out_at: string | null;
  kiosk_id: string | null;
}

/** AttendanceLogOut: confidence_score is a string (Pydantic JSON mode). */
export interface AttendanceLogOut {
  id: string;
  visit_id: string;
  visitor_id: string;
  event_type: AttendanceEventType;
  event_timestamp: string;
  kiosk_id: string | null;
  confidence_score: string | null;
  is_correction: boolean;
  correction_of_id: string | null;
  correction_reason: string | null;
  created_at: string;
}

export interface AttendanceListQuery {
  page?: number;
  page_size?: number;
  visitor_id?: string;
  event_type?: AttendanceEventType;
  date_from?: string;
  date_to?: string;
  kiosk_id?: string;
}

export interface AttendanceCorrectionRequest {
  corrected_event_type: AttendanceEventType;
  corrected_timestamp: string;
  reason: string;
}

/* -------------------------------------------------------------------------- */
/* Face recognition                                                           */
/* -------------------------------------------------------------------------- */

/** Multipart fields for POST /face/enroll (field name `image` is the file). */
export interface FaceEnrollFormMeta {
  visitor_id?: string | null;
  full_name?: string | null;
  identity_number?: string | null;
  company_name?: string | null;
  phone_number?: string | null;
  email?: string | null;
  consent_granted?: boolean;
  consent_policy_version?: string;
  replace_existing?: boolean;
}

export interface FaceEnrollResult {
  visitor: VisitorSummary;
  profile_id: string;
  model_version: string;
  embedding_version: string;
  consent_recorded: boolean;
  duplicate_review: boolean;
}

/** `confidence` is a number here (jsonable_encoder). */
export interface FaceIdentifyResult {
  match_status: MatchStatus;
  visitor: VisitorSummary | null;
  confidence: number | null;
  review_required: boolean;
  active_visit_id: string | null;
  active_visit_status: string | null;
}

export interface FaceVerifyResult {
  matched: boolean;
  confidence: number;
  visitor_id: string;
}

export interface LivenessResult {
  passed: boolean;
  score: number | null;
  provider: string;
}

/* -------------------------------------------------------------------------- */
/* Reports                                                                    */
/* -------------------------------------------------------------------------- */

export interface DashboardOut {
  total_visitors: number;
  active_visitors: number;
  visitors_currently_inside: number;
  today_check_ins: number;
  today_check_outs: number;
  pending_visits: number;
  active_kiosks: number;
  generated_at: string;
  timezone: string;
}

export interface DailyAttendanceRow {
  hour: number;
  check_ins: number;
  check_outs: number;
}

export interface DailyReportOut {
  /** `YYYY-MM-DD` in the business timezone. */
  date: string;
  timezone: string;
  total_check_ins: number;
  total_check_outs: number;
  rows: DailyAttendanceRow[];
}

export interface MonthlyAttendanceRow {
  /** `YYYY-MM-DD` in the business timezone. */
  date: string;
  check_ins: number;
  check_outs: number;
}

export interface MonthlyReportOut {
  year: number;
  month: number;
  timezone: string;
  total_check_ins: number;
  total_check_outs: number;
  rows: MonthlyAttendanceRow[];
}

export interface VisitorReportRow {
  visitor_id: string;
  visitor_code: string;
  full_name: string;
  company_name: string | null;
  visit_count: number;
  last_visit_at: string | null;
}

export interface VisitorReportOut {
  items: VisitorReportRow[];
  total: number;
}

export interface DailyReportQuery {
  date?: string;
}

export interface MonthlyReportQuery {
  year?: number;
  month?: number;
}

export interface VisitorReportQuery {
  search?: string;
  /** 1..2000, default 500. */
  limit?: number;
}

export interface ReportExportQuery {
  report_type?: ReportType;
  format?: ReportFormat;
  date_from?: string;
  date_to?: string;
  year?: number;
  month?: number;
}

/* -------------------------------------------------------------------------- */
/* Administration                                                             */
/* -------------------------------------------------------------------------- */

export interface UserCreate {
  username: string;
  email: string;
  password: string;
  full_name: string;
  role?: UserRole;
}

export interface UserUpdate {
  email?: string | null;
  full_name?: string | null;
  role?: UserRole | null;
  is_active?: boolean | null;
  password?: string | null;
}

export interface UserListQuery {
  page?: number;
  page_size?: number;
  role?: string;
  is_active?: boolean;
}

export interface AuditLogOut {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  description: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogListQuery {
  page?: number;
  page_size?: number;
  user_id?: string;
  action?: string;
  entity_type?: string;
}

/* -------------------------------------------------------------------------- */
/* Convenience unions                                                         */
/* -------------------------------------------------------------------------- */

export interface Paginated<T> {
  data: T[];
  meta: PaginationMeta;
}
