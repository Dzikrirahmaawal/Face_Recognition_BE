"""Initial Microsoft SQL Server schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-10

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("username", mssql.NVARCHAR(length=50), nullable=False),
        sa.Column("email", mssql.NVARCHAR(length=255), nullable=False),
        sa.Column("password_hash", mssql.NVARCHAR(length=255), nullable=False),
        sa.Column("full_name", mssql.NVARCHAR(length=150), nullable=False),
        sa.Column("role", mssql.NVARCHAR(length=30), nullable=False, server_default=sa.text("'VIEWER'")),
        sa.Column("is_active", mssql.BIT(), nullable=False, server_default=sa.text("1")),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_login_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("updated_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "employees",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("employee_code", mssql.NVARCHAR(length=30), nullable=False),
        sa.Column("full_name", mssql.NVARCHAR(length=150), nullable=False),
        sa.Column("department", mssql.NVARCHAR(length=100), nullable=True),
        sa.Column("email", mssql.NVARCHAR(length=255), nullable=True),
        sa.Column("phone_number", mssql.NVARCHAR(length=30), nullable=True),
        sa.Column("is_active", mssql.BIT(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("updated_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.PrimaryKeyConstraint("id", name="pk_employees"),
        sa.UniqueConstraint("employee_code", name="uq_employees_employee_code"),
    )
    op.create_index("ix_employees_full_name", "employees", ["full_name"])
    op.create_index("ix_employees_department", "employees", ["department"])
    op.create_index("ix_employees_is_active", "employees", ["is_active"])
    op.create_index(
        "uq_employees_email_not_null",
        "employees",
        ["email"],
        unique=True,
        mssql_where=sa.text("email IS NOT NULL"),
    )

    op.create_table(
        "visitors",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("visitor_code", mssql.NVARCHAR(length=30), nullable=False),
        sa.Column("full_name", mssql.NVARCHAR(length=150), nullable=False),
        sa.Column("identity_number", mssql.NVARCHAR(length=64), nullable=True),
        sa.Column("company_name", mssql.NVARCHAR(length=150), nullable=True),
        sa.Column("phone_number", mssql.NVARCHAR(length=30), nullable=True),
        sa.Column("email", mssql.NVARCHAR(length=255), nullable=True),
        sa.Column("is_active", mssql.BIT(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("updated_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.PrimaryKeyConstraint("id", name="pk_visitors"),
        sa.UniqueConstraint("visitor_code", name="uq_visitors_visitor_code"),
    )
    op.create_index("ix_visitors_full_name", "visitors", ["full_name"])
    op.create_index("ix_visitors_phone_number", "visitors", ["phone_number"])
    op.create_index("ix_visitors_email", "visitors", ["email"])
    op.create_index("ix_visitors_is_active", "visitors", ["is_active"])
    op.create_index(
        "uq_visitors_identity_number_not_null",
        "visitors",
        ["identity_number"],
        unique=True,
        mssql_where=sa.text("identity_number IS NOT NULL"),
    )

    op.create_table(
        "kiosks",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("kiosk_code", mssql.NVARCHAR(length=30), nullable=False),
        sa.Column("device_name", mssql.NVARCHAR(length=150), nullable=False),
        sa.Column("device_token_hash", mssql.NVARCHAR(length=64), nullable=False),
        sa.Column("location", mssql.NVARCHAR(length=150), nullable=True),
        sa.Column("is_active", mssql.BIT(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_seen_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("updated_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.PrimaryKeyConstraint("id", name="pk_kiosks"),
        sa.UniqueConstraint("kiosk_code", name="uq_kiosks_kiosk_code"),
        sa.UniqueConstraint("device_token_hash", name="uq_kiosks_device_token_hash"),
    )
    op.create_index("ix_kiosks_is_active", "kiosks", ["is_active"])
    op.create_index("ix_kiosks_last_seen_at", "kiosks", ["last_seen_at"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("user_id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("token_hash", mssql.NVARCHAR(length=64), nullable=False),
        sa.Column("jti", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("expires_at", mssql.DATETIMEOFFSET(), nullable=False),
        sa.Column("revoked_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("replaced_by_id", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("ip_address", mssql.NVARCHAR(length=45), nullable=True),
        sa.Column("user_agent", mssql.NVARCHAR(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        sa.UniqueConstraint("jti", name="uq_refresh_tokens_jti"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    op.create_table(
        "face_profiles",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("visitor_id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("embedding_data", mssql.VARBINARY(), nullable=True),
        sa.Column("model_version", mssql.NVARCHAR(length=50), nullable=False),
        sa.Column("embedding_version", mssql.NVARCHAR(length=20), nullable=False),
        sa.Column("is_active", mssql.BIT(), nullable=False, server_default=sa.text("1")),
        sa.Column("active_profile_key", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("enrolled_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("updated_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("deleted_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("deletion_reason", mssql.NVARCHAR(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["visitor_id"], ["visitors.id"], name="fk_face_profiles_visitor_id_visitors", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_face_profiles"),
    )
    op.create_index("ix_face_profiles_visitor_id", "face_profiles", ["visitor_id"])
    op.create_index("ix_face_profiles_is_active", "face_profiles", ["is_active"])
    op.create_index(
        "uq_face_profiles_active_key",
        "face_profiles",
        ["active_profile_key"],
        unique=True,
        mssql_where=sa.text("active_profile_key IS NOT NULL"),
    )

    op.create_table(
        "visits",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("visitor_id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("purpose", mssql.NVARCHAR(length=255), nullable=True),
        sa.Column("host_employee_id", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("visit_status", mssql.NVARCHAR(length=20), nullable=False, server_default=sa.text("'WAITING'")),
        sa.Column("check_in_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("check_out_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("active_visit_key", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("updated_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.CheckConstraint(
            "(visit_status IN ('WAITING','CHECKED_IN') AND active_visit_key = visitor_id) "
            "OR (visit_status IN ('CHECKED_OUT','CANCELLED') AND active_visit_key IS NULL)",
            name="ck_visits_active_key_matches_status",
        ),
        sa.ForeignKeyConstraint(
            ["visitor_id"], ["visitors.id"], name="fk_visits_visitor_id_visitors", ondelete="NO ACTION"
        ),
        sa.ForeignKeyConstraint(
            ["host_employee_id"], ["employees.id"], name="fk_visits_host_employee_id_employees", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_visits"),
    )
    op.create_index("ix_visits_visitor_id", "visits", ["visitor_id"])
    op.create_index("ix_visits_host_employee_id", "visits", ["host_employee_id"])
    op.create_index("ix_visits_visit_status", "visits", ["visit_status"])
    op.create_index("ix_visits_check_in_at", "visits", ["check_in_at"])
    op.create_index(
        "uq_visits_active_key",
        "visits",
        ["active_visit_key"],
        unique=True,
        mssql_where=sa.text("active_visit_key IS NOT NULL"),
    )
    op.create_index(
        "uq_visits_one_waiting_per_visitor",
        "visits",
        ["visitor_id"],
        unique=True,
        mssql_where=sa.text("visit_status = 'WAITING'"),
    )
    op.create_index(
        "uq_visits_one_checked_in_per_visitor",
        "visits",
        ["visitor_id"],
        unique=True,
        mssql_where=sa.text("visit_status = 'CHECKED_IN'"),
    )

    op.create_table(
        "attendance_logs",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("visit_id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("visitor_id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("event_type", mssql.NVARCHAR(length=20), nullable=False),
        sa.Column("event_timestamp", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("kiosk_id", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("confidence_score", mssql.DECIMAL(5, 4), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("is_correction", mssql.BIT(), nullable=False, server_default=sa.text("0")),
        sa.Column("correction_of_id", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("correction_reason", mssql.NVARCHAR(length=255), nullable=True),
        sa.Column("recorded_by_user_id", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("event_unique_key", mssql.NVARCHAR(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["visit_id"], ["visits.id"], name="fk_attendance_logs_visit_id_visits", ondelete="NO ACTION"
        ),
        sa.ForeignKeyConstraint(
            ["visitor_id"], ["visitors.id"], name="fk_attendance_logs_visitor_id_visitors", ondelete="NO ACTION"
        ),
        sa.ForeignKeyConstraint(
            ["kiosk_id"], ["kiosks.id"], name="fk_attendance_logs_kiosk_id_kiosks", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["correction_of_id"],
            ["attendance_logs.id"],
            name="fk_attendance_logs_correction_of_id_attendance_logs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"], ["users.id"], name="fk_attendance_logs_recorded_by_user_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attendance_logs"),
    )
    op.create_index("ix_attendance_logs_visit_id", "attendance_logs", ["visit_id"])
    op.create_index("ix_attendance_logs_visitor_id", "attendance_logs", ["visitor_id"])
    op.create_index("ix_attendance_logs_event_timestamp", "attendance_logs", ["event_timestamp"])
    op.create_index("ix_attendance_logs_kiosk_id", "attendance_logs", ["kiosk_id"])
    op.create_index(
        "uq_attendance_logs_event_key",
        "attendance_logs",
        ["event_unique_key"],
        unique=True,
        mssql_where=sa.text("event_unique_key IS NOT NULL"),
    )

    op.create_table(
        "consent_records",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("visitor_id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("consent_type", mssql.NVARCHAR(length=40), nullable=False),
        sa.Column("policy_version", mssql.NVARCHAR(length=50), nullable=False),
        sa.Column("consent_status", mssql.NVARCHAR(length=20), nullable=False),
        sa.Column("consented_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("withdrawn_at", mssql.DATETIMEOFFSET(), nullable=True),
        sa.Column("recorded_by", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.ForeignKeyConstraint(
            ["visitor_id"], ["visitors.id"], name="fk_consent_records_visitor_id_visitors", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["users.id"], name="fk_consent_records_recorded_by_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consent_records"),
    )
    op.create_index("ix_consent_records_visitor_id", "consent_records", ["visitor_id"])
    op.create_index("ix_consent_records_type_status", "consent_records", ["consent_type", "consent_status"])
    op.create_index("ix_consent_records_created_at", "consent_records", ["created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("user_id", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("action", mssql.NVARCHAR(length=100), nullable=False),
        sa.Column("entity_type", mssql.NVARCHAR(length=100), nullable=True),
        sa.Column("entity_id", mssql.NVARCHAR(length=100), nullable=True),
        sa.Column("description", mssql.NVARCHAR(length=1000), nullable=True),
        sa.Column("ip_address", mssql.NVARCHAR(length=45), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_logs_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column("key", mssql.NVARCHAR(length=128), nullable=False),
        sa.Column("scope", mssql.NVARCHAR(length=100), nullable=False),
        sa.Column("request_hash", mssql.NVARCHAR(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", mssql.NVARCHAR(), nullable=False),
        sa.Column("user_id", mssql.UNIQUEIDENTIFIER(), nullable=True),
        sa.Column("created_at", mssql.DATETIMEOFFSET(), nullable=False, server_default=sa.text("SYSUTCDATETIME()")),
        sa.Column("expires_at", mssql.DATETIMEOFFSET(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("key", name="uq_idempotency_records_key"),
    )
    op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")

    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_consent_records_created_at", table_name="consent_records")
    op.drop_index("ix_consent_records_type_status", table_name="consent_records")
    op.drop_index("ix_consent_records_visitor_id", table_name="consent_records")
    op.drop_table("consent_records")

    op.drop_index("uq_attendance_logs_event_key", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_kiosk_id", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_event_timestamp", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_visitor_id", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_visit_id", table_name="attendance_logs")
    op.drop_table("attendance_logs")

    op.drop_index("uq_visits_one_checked_in_per_visitor", table_name="visits")
    op.drop_index("uq_visits_one_waiting_per_visitor", table_name="visits")
    op.drop_index("uq_visits_active_key", table_name="visits")
    op.drop_index("ix_visits_check_in_at", table_name="visits")
    op.drop_index("ix_visits_visit_status", table_name="visits")
    op.drop_index("ix_visits_host_employee_id", table_name="visits")
    op.drop_index("ix_visits_visitor_id", table_name="visits")
    op.drop_table("visits")

    op.drop_index("uq_face_profiles_active_key", table_name="face_profiles")
    op.drop_index("ix_face_profiles_is_active", table_name="face_profiles")
    op.drop_index("ix_face_profiles_visitor_id", table_name="face_profiles")
    op.drop_table("face_profiles")

    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_kiosks_last_seen_at", table_name="kiosks")
    op.drop_index("ix_kiosks_is_active", table_name="kiosks")
    op.drop_table("kiosks")

    op.drop_index("uq_visitors_identity_number_not_null", table_name="visitors")
    op.drop_index("ix_visitors_is_active", table_name="visitors")
    op.drop_index("ix_visitors_email", table_name="visitors")
    op.drop_index("ix_visitors_phone_number", table_name="visitors")
    op.drop_index("ix_visitors_full_name", table_name="visitors")
    op.drop_table("visitors")

    op.drop_index("uq_employees_email_not_null", table_name="employees")
    op.drop_index("ix_employees_is_active", table_name="employees")
    op.drop_index("ix_employees_department", table_name="employees")
    op.drop_index("ix_employees_full_name", table_name="employees")
    op.drop_table("employees")

    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_table("users")
