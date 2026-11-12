from __future__ import annotations

from tests.helpers import enroll_visitor


async def _attendance_fixture(client, kiosk_headers):
    enrolled = await enroll_visitor(client, kiosk_headers, seed=101)
    visitor_id = enrolled["visitor"]["id"]
    await client.post(
        "/api/v1/attendance/check-in",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    await client.post(
        "/api/v1/attendance/check-out",
        headers=kiosk_headers,
        json={"visitor_id": visitor_id, "method": "FACE"},
    )
    return visitor_id


async def test_dashboard_and_reports(client, kiosk_headers, admin_headers):
    await _attendance_fixture(client, kiosk_headers)

    dashboard = await client.get("/api/v1/reports/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    data = dashboard.json()["data"]
    assert data["total_visitors"] == 1
    assert data["today_check_ins"] == 1
    assert data["today_check_outs"] == 1
    assert data["timezone"] == "Asia/Jakarta"

    daily = await client.get("/api/v1/reports/attendance/daily", headers=admin_headers)
    assert daily.status_code == 200
    assert daily.json()["data"]["total_check_ins"] == 1

    monthly = await client.get("/api/v1/reports/attendance/monthly", headers=admin_headers)
    assert monthly.status_code == 200
    assert monthly.json()["data"]["total_check_outs"] == 1

    visitors = await client.get("/api/v1/reports/visitors", headers=admin_headers)
    assert visitors.status_code == 200
    assert visitors.json()["data"]["total"] == 1
    assert visitors.json()["data"]["items"][0]["visit_count"] == 1


async def test_csv_and_xlsx_export(client, kiosk_headers, admin_headers):
    await _attendance_fixture(client, kiosk_headers)
    csv_response = await client.get(
        "/api/v1/reports/attendance/export?report_type=visitors&format=csv",
        headers=admin_headers,
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment" in csv_response.headers["content-disposition"]
    assert b"visitor_code" in csv_response.content

    xlsx_response = await client.get(
        "/api/v1/reports/attendance/export?report_type=daily&format=xlsx",
        headers=admin_headers,
    )
    assert xlsx_response.status_code == 200
    assert "spreadsheetml" in xlsx_response.headers["content-type"]
    assert len(xlsx_response.content) > 100


async def test_viewer_can_read_reports_but_not_attendance_write(client, kiosk_headers, viewer_headers):
    await _attendance_fixture(client, kiosk_headers)
    response = await client.get("/api/v1/reports/dashboard", headers=viewer_headers)
    assert response.status_code == 200
