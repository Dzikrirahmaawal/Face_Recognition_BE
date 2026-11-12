from __future__ import annotations


async def test_visitor_crud_and_soft_delete(client, admin_headers):
    created = await client.post(
        "/api/v1/visitors",
        headers=admin_headers,
        json={
            "full_name": "Alice Visitor",
            "identity_number": "ID-001",
            "company_name": "Acme",
            "phone_number": "081200000001",
            "email": "alice@example.com",
        },
    )
    assert created.status_code == 201, created.text
    visitor = created.json()["data"]
    visitor_id = visitor["id"]
    assert visitor["visitor_code"].startswith("VIS-")

    listed = await client.get("/api/v1/visitors?search=Alice", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    fetched = await client.get(f"/api/v1/visitors/{visitor_id}", headers=admin_headers)
    assert fetched.status_code == 200

    updated = await client.put(
        f"/api/v1/visitors/{visitor_id}",
        headers=admin_headers,
        json={"company_name": "Acme Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["company_name"] == "Acme Updated"

    deleted = await client.delete(f"/api/v1/visitors/{visitor_id}", headers=admin_headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["is_active"] is False


async def test_duplicate_identity_number_conflict(client, admin_headers):
    payload = {"full_name": "Duplicate ID", "identity_number": "ID-DUP"}
    first = await client.post("/api/v1/visitors", headers=admin_headers, json=payload)
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/visitors",
        headers=admin_headers,
        json={"full_name": "Duplicate ID 2", "identity_number": "ID-DUP"},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "VISITOR_EXISTS"


async def test_viewer_cannot_create_visitor(client, viewer_headers):
    response = await client.post(
        "/api/v1/visitors", headers=viewer_headers, json={"full_name": "Nope"}
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


async def test_visitor_not_found(client, admin_headers):
    response = await client.get(
        "/api/v1/visitors/00000000-0000-0000-0000-000000000000", headers=admin_headers
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "VISITOR_NOT_FOUND"
