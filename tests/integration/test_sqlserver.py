from __future__ import annotations

import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip(
        "Set TEST_DATABASE_URL (and ALLOW_SQLSERVER_INTEGRATION_TESTS=true) to run SQL Server integration tests",
        allow_module_level=True,
    )
if os.environ.get("ALLOW_SQLSERVER_INTEGRATION_TESTS") != "true":
    pytest.skip(
        "Set ALLOW_SQLSERVER_INTEGRATION_TESTS=true to allow destructive migration tests",
        allow_module_level=True,
    )

from sqlalchemy import create_engine, func, inspect, select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.dependencies import Actor  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.core.types import ensure_utc, utcnow  # noqa: E402
from app.models import (  # noqa: E402
    AttendanceEventType,
    AttendanceLog,
    AttendanceMethod,
    FaceProfile,
    Visit,
    VisitStatus,
    Visitor,
)
from app.schemas.attendance import CheckInRequest  # noqa: E402
from app.services import attendance_service, report_service  # noqa: E402

pytestmark = pytest.mark.sqlserver

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _alembic_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": TEST_DATABASE_URL,
            "APP_ENV": "test",
            "ALLOW_SQLITE_FOR_TESTS": "false",
            "FACE_RECOGNITION_PROVIDER": "mock",
            "FACE_LIVENESS_PROVIDER": "mock",
        }
    )
    return env


def _run_alembic(action: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *action.split()],
        cwd=PROJECT_ROOT,
        env=_alembic_env(),
        check=True,
    )


@pytest.fixture(scope="module")
def sql_engine():
    _run_alembic("upgrade head")
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
        _run_alembic("downgrade base")


def _new_visitor(session: Session, name: str) -> Visitor:
    visitor = Visitor(visitor_code=f"VIS-{uuid.uuid4().hex[:10]}", full_name=name, is_active=True)
    session.add(visitor)
    session.commit()
    session.refresh(visitor)
    return visitor


def test_migration_creates_schema_and_filtered_indexes(sql_engine):
    inspector = inspect(sql_engine)
    tables = set(inspector.get_table_names())
    expected = {
        "users",
        "refresh_tokens",
        "visitors",
        "face_profiles",
        "visits",
        "attendance_logs",
        "employees",
        "consent_records",
        "audit_logs",
        "kiosks",
        "idempotency_records",
    }
    assert expected <= tables

    visit_indexes = {index["name"] for index in inspector.get_indexes("visits")}
    assert {"uq_visits_active_key", "uq_visits_one_checked_in_per_visitor"} <= visit_indexes

    profile_indexes = {index["name"] for index in inspector.get_indexes("face_profiles")}
    assert "uq_face_profiles_active_key" in profile_indexes

    attendance_indexes = {index["name"] for index in inspector.get_indexes("attendance_logs")}
    assert "uq_attendance_logs_event_key" in attendance_indexes


def test_active_visit_unique_constraint(sql_engine):
    with Session(sql_engine) as session:
        visitor = _new_visitor(session, "Active Visit Constraint")
        first = Visit(
            visitor_id=visitor.id,
            visit_status=VisitStatus.CHECKED_IN,
            check_in_at=utcnow(),
            active_visit_key=visitor.id,
        )
        session.add(first)
        session.commit()

        second = Visit(
            visitor_id=visitor.id,
            visit_status=VisitStatus.CHECKED_IN,
            check_in_at=utcnow(),
            active_visit_key=visitor.id,
        )
        session.add(second)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_multiple_closed_visits_are_allowed(sql_engine):
    with Session(sql_engine) as session:
        visitor = _new_visitor(session, "Closed Visits")
        for _ in range(2):
            session.add(
                Visit(
                    visitor_id=visitor.id,
                    visit_status=VisitStatus.CHECKED_OUT,
                    check_in_at=utcnow(),
                    check_out_at=utcnow(),
                    active_visit_key=None,
                )
            )
        session.commit()
        count = session.scalar(
            select(func.count()).select_from(Visit).where(Visit.visitor_id == visitor.id)
        )
        assert count == 2


def test_active_face_profile_unique_constraint(sql_engine):
    with Session(sql_engine) as session:
        visitor = _new_visitor(session, "Face Profile Constraint")
        first = FaceProfile(
            visitor_id=visitor.id,
            embedding_data=b"ciphertext",
            model_version="test",
            embedding_version="1",
            is_active=True,
            active_profile_key=visitor.id,
            enrolled_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(first)
        session.commit()

        second = FaceProfile(
            visitor_id=visitor.id,
            embedding_data=b"ciphertext-2",
            model_version="test",
            embedding_version="1",
            is_active=True,
            active_profile_key=visitor.id,
            enrolled_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(second)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_attendance_event_unique_constraint(sql_engine):
    with Session(sql_engine) as session:
        visitor = _new_visitor(session, "Attendance Constraint")
        visit = Visit(
            visitor_id=visitor.id,
            visit_status=VisitStatus.CHECKED_IN,
            check_in_at=utcnow(),
            active_visit_key=visitor.id,
        )
        session.add(visit)
        session.commit()
        session.refresh(visit)

        key = f"{visit.id}:CHECK_IN"
        session.add(
            AttendanceLog(
                visit_id=visit.id,
                visitor_id=visitor.id,
                event_type=AttendanceEventType.CHECK_IN,
                event_timestamp=utcnow(),
                event_unique_key=key,
            )
        )
        session.commit()

        session.add(
            AttendanceLog(
                visit_id=visit.id,
                visitor_id=visitor.id,
                event_type=AttendanceEventType.CHECK_IN,
                event_timestamp=utcnow(),
                event_unique_key=key,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_concurrent_check_in_allows_exactly_one(sql_engine):
    with Session(sql_engine) as session:
        visitor = _new_visitor(session, "Concurrent Visitor")
        visitor_id = visitor.id

    results: list[int] = []
    unexpected: list[BaseException] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        session = Session(sql_engine)
        try:
            barrier.wait(timeout=10)
            status, _ = attendance_service.check_in(
                session,
                data=CheckInRequest(visitor_id=visitor_id, method=AttendanceMethod.MANUAL),
                actor=Actor(),
                ip_address="127.0.0.1",
                idempotency_key=None,
            )
            results.append(status)
        except AppError as exc:
            results.append(exc.status_code)
        except BaseException as exc:  # noqa: BLE001
            unexpected.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not unexpected, unexpected
    assert sorted(results) == [201, 409]


def test_visitor_report_group_by_compatible_with_sqlserver(sql_engine):
    marker = f"rpt-{uuid.uuid4().hex[:8]}"
    older = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    newer = datetime(2026, 1, 5, 6, 7, tzinfo=timezone.utc)

    with Session(sql_engine) as session:
        with_visits = _new_visitor(session, f"Report {marker} With Visits")
        without_visits = _new_visitor(session, f"Report {marker} Without Visits")
        with_visits_id = with_visits.id
        without_visits_id = without_visits.id

        session.add_all(
            [
                Visit(
                    visitor_id=with_visits_id,
                    visit_status=VisitStatus.CHECKED_OUT,
                    check_in_at=older,
                    check_out_at=older,
                    active_visit_key=None,
                    created_at=older,
                    updated_at=older,
                ),
                Visit(
                    visitor_id=with_visits_id,
                    visit_status=VisitStatus.CHECKED_OUT,
                    check_in_at=newer,
                    check_out_at=newer,
                    active_visit_key=None,
                    created_at=newer,
                    updated_at=newer,
                ),
            ]
        )
        session.commit()

        # This executes the real query against SQL Server. Before the fix it
        # raised a GROUP BY ProgrammingError (SQL Server error 8120).
        report = report_service.visitor_report(session, search=marker, limit=50)

    assert report["total"] == 2
    items = {str(item["visitor_id"]): item for item in report["items"]}
    assert set(items) == {str(with_visits_id), str(without_visits_id)}

    with_item = items[str(with_visits_id)]
    assert with_item["visit_count"] == 2
    assert ensure_utc(with_item["last_visit_at"]) == ensure_utc(newer)

    without_item = items[str(without_visits_id)]
    assert without_item["visit_count"] == 0
    assert without_item["last_visit_at"] is None
