from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from sqlalchemy import false, func, or_, select, true
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.types import ensure_utc, utcnow
from app.models.attendance import AttendanceLog
from app.models.enums import AttendanceEventType, VisitStatus
from app.models.kiosk import Kiosk
from app.models.visit import Visit
from app.models.visitor import Visitor


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.TIMEZONE)


def local_today() -> date:
    return utcnow().astimezone(_tz()).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    tz = _tz()
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = (datetime.combine(day, time.min, tzinfo=tz) + timedelta(days=1)).astimezone(timezone.utc)
    return start, end


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    tz = _tz()
    start = datetime(year, month, 1, tzinfo=tz).astimezone(timezone.utc)
    if month == 12:
        next_start = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        next_start = datetime(year, month + 1, 1, tzinfo=tz)
    return start, next_start.astimezone(timezone.utc)


def _to_local(value: datetime) -> datetime:
    normalized = ensure_utc(value) or value
    return normalized.astimezone(_tz())


def _count(db: Session, stmt) -> int:  # noqa: ANN001
    return int(db.scalar(stmt) or 0)


def dashboard(db: Session) -> dict:
    today = local_today()
    start, end = day_bounds(today)
    total_visitors = _count(db, select(func.count()).select_from(Visitor))
    active_visitors = _count(db, select(func.count()).select_from(Visitor).where(Visitor.is_active == true()))
    inside = _count(
        db,
        select(func.count()).select_from(Visit).where(Visit.visit_status == VisitStatus.CHECKED_IN),
    )
    pending = _count(
        db,
        select(func.count()).select_from(Visit).where(Visit.visit_status == VisitStatus.WAITING),
    )
    active_kiosks = _count(db, select(func.count()).select_from(Kiosk).where(Kiosk.is_active == true()))
    base = (
        AttendanceLog.is_correction == false(),
        AttendanceLog.event_timestamp >= start,
        AttendanceLog.event_timestamp < end,
    )
    check_ins = _count(
        db,
        select(func.count())
        .select_from(AttendanceLog)
        .where(*base, AttendanceLog.event_type == AttendanceEventType.CHECK_IN),
    )
    check_outs = _count(
        db,
        select(func.count())
        .select_from(AttendanceLog)
        .where(*base, AttendanceLog.event_type == AttendanceEventType.CHECK_OUT),
    )
    return {
        "total_visitors": total_visitors,
        "active_visitors": active_visitors,
        "visitors_currently_inside": inside,
        "today_check_ins": check_ins,
        "today_check_outs": check_outs,
        "pending_visits": pending,
        "active_kiosks": active_kiosks,
        "generated_at": utcnow(),
        "timezone": settings.TIMEZONE,
    }


def _events_between(db: Session, start: datetime, end: datetime) -> list[AttendanceLog]:
    stmt = select(AttendanceLog).where(
        AttendanceLog.is_correction == false(),
        AttendanceLog.event_timestamp >= start,
        AttendanceLog.event_timestamp < end,
    )
    return list(db.scalars(stmt).all())


def daily_report(db: Session, day: date) -> dict:
    start, end = day_bounds(day)
    events = _events_between(db, start, end)
    rows: dict[int, dict[str, int]] = defaultdict(lambda: {"check_ins": 0, "check_outs": 0})
    for event in events:
        hour = _to_local(event.event_timestamp).hour
        if event.event_type == AttendanceEventType.CHECK_IN:
            rows[hour]["check_ins"] += 1
        else:
            rows[hour]["check_outs"] += 1
    return {
        "date": day,
        "timezone": settings.TIMEZONE,
        "total_check_ins": sum(row["check_ins"] for row in rows.values()),
        "total_check_outs": sum(row["check_outs"] for row in rows.values()),
        "rows": [
            {"hour": hour, "check_ins": rows[hour]["check_ins"], "check_outs": rows[hour]["check_outs"]}
            for hour in sorted(rows)
        ],
    }


def monthly_report(db: Session, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    events = _events_between(db, start, end)
    rows: dict[date, dict[str, int]] = defaultdict(lambda: {"check_ins": 0, "check_outs": 0})
    for event in events:
        day = _to_local(event.event_timestamp).date()
        if event.event_type == AttendanceEventType.CHECK_IN:
            rows[day]["check_ins"] += 1
        else:
            rows[day]["check_outs"] += 1
    return {
        "year": year,
        "month": month,
        "timezone": settings.TIMEZONE,
        "total_check_ins": sum(row["check_ins"] for row in rows.values()),
        "total_check_outs": sum(row["check_outs"] for row in rows.values()),
        "rows": [
            {"date": day, "check_ins": rows[day]["check_ins"], "check_outs": rows[day]["check_outs"]}
            for day in sorted(rows)
        ],
    }


def visitor_report(db: Session, *, search: str | None = None, limit: int = 500) -> dict:
    count_stmt = select(func.count()).select_from(Visitor)
    visit_stats = (
        select(
            Visit.visitor_id.label("visitor_id"),
            func.count(Visit.id).label("visit_count"),
            func.max(Visit.created_at).label("last_visit_at"),
        )
        .group_by(Visit.visitor_id)
        .subquery()
    )
    stmt = (
        select(
            Visitor,
            func.coalesce(visit_stats.c.visit_count, 0).label("visit_count"),
            visit_stats.c.last_visit_at,
        )
        .outerjoin(visit_stats, visit_stats.c.visitor_id == Visitor.id)
        .order_by(
            func.coalesce(visit_stats.c.visit_count, 0).desc(),
            Visitor.full_name.asc(),
        )
        .limit(max(1, min(limit, 2000)))
    )
    if search:
        like = f"%{search}%"
        condition = or_(Visitor.full_name.ilike(like), Visitor.visitor_code.ilike(like))
        count_stmt = count_stmt.where(condition)
        stmt = stmt.where(condition)
    total = _count(db, count_stmt)
    items = [
        {
            "visitor_id": visitor.id,
            "visitor_code": visitor.visitor_code,
            "full_name": visitor.full_name,
            "company_name": visitor.company_name,
            "visit_count": int(visit_count),
            "last_visit_at": last_visit_at,
        }
        for visitor, visit_count, last_visit_at in db.execute(stmt).all()
    ]
    return {"items": items, "total": total}


def export_report(
    db: Session,
    *,
    report_type: str,
    file_format: str,
    date_from: date | None,
    date_to: date | None,
    year: int | None,
    month: int | None,
) -> tuple[bytes, str, str]:
    if report_type == "visitors":
        data = visitor_report(db, limit=2000)
        headers = ["visitor_id", "visitor_code", "full_name", "company_name", "visit_count", "last_visit_at"]
        rows = [
            [
                str(item["visitor_id"]),
                item["visitor_code"],
                item["full_name"],
                item["company_name"] or "",
                item["visit_count"],
                item["last_visit_at"].isoformat() if item["last_visit_at"] else "",
            ]
            for item in data["items"]
        ]
        filename = f"visitors-report-{local_today().isoformat()}"
    elif report_type == "monthly":
        y = year or local_today().year
        m = month or local_today().month
        data = monthly_report(db, y, m)
        headers = ["date", "check_ins", "check_outs"]
        rows = [[row["date"].isoformat(), row["check_ins"], row["check_outs"]] for row in data["rows"]]
        filename = f"attendance-monthly-{y}-{m:02d}"
    else:
        end_day = date_to or local_today()
        start_day = date_from or (end_day - timedelta(days=29))
        headers = ["date", "hour", "check_ins", "check_outs"]
        rows = []
        cursor = start_day
        while cursor <= end_day:
            report = daily_report(db, cursor)
            for row in report["rows"]:
                rows.append([cursor.isoformat(), row["hour"], row["check_ins"], row["check_outs"]])
            cursor += timedelta(days=1)
        filename = f"attendance-daily-{start_day.isoformat()}-to-{end_day.isoformat()}"

    if file_format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Report"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return (
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{filename}.xlsx",
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", f"{filename}.csv"
