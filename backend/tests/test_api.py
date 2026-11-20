import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Department


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ACLEDA" in data["app"]


@pytest.mark.asyncio
async def test_scalar_api_reference(client: AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200
    html = response.text.lower()
    assert "scalar" in html
    assert "swagger-ui" not in html


@pytest.mark.asyncio
async def test_auth_workflow(client: AsyncClient):
    admin_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@aub.edu.kh", "password": "Admin@AUB2026"},
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    reg_payload = {
        "email": "test.staff@aub.edu.kh",
        "password": "Password@123",
        "full_name": "Test Academic Staff",
        "student_or_staff_id": "AUB-5801",
        "roles": ["Staff"],
    }

    # Public sign-up is disabled so an anonymous user cannot grant themselves admin.
    unauth_reg = await client.post("/api/v1/auth/register", json=reg_payload)
    assert unauth_reg.status_code == 401

    reg_res = await client.post(
        "/api/v1/auth/register", json=reg_payload, headers=admin_headers
    )
    assert reg_res.status_code == 200
    assert reg_res.json()["email"] == "test.staff@aub.edu.kh"
    assert [role["role_name"] for role in reg_res.json()["roles"]] == ["Staff"]

    bad_role = await client.post(
        "/api/v1/auth/register",
        json={**reg_payload, "email": "bad.role@aub.edu.kh", "roles": ["Superuser"]},
        headers=admin_headers,
    )
    assert bad_role.status_code == 400

    dup_res = await client.post(
        "/api/v1/auth/register", json=reg_payload, headers=admin_headers
    )
    assert dup_res.status_code == 400

    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": " TEST.STAFF@AUB.EDU.KH ", "password": "Password@123"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "test.staff@aub.edu.kh"

    # A refresh token must never be accepted as an access token.
    refresh_as_access = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert refresh_as_access.status_code == 401

    refresh_res = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_res.status_code == 200
    refreshed = refresh_res.json()
    assert refreshed["access_token"] != access_token
    me_after_refresh = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert me_after_refresh.status_code == 200
    assert me_after_refresh.json()["email"] == "test.staff@aub.edu.kh"


@pytest.mark.asyncio
async def test_login_rate_limit(client: AsyncClient):
    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "rate.limit@aub.edu.kh", "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        data={"username": "rate.limit@aub.edu.kh", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "300"


@pytest.mark.asyncio
async def test_document_and_meeting_lifecycle(client: AsyncClient, db_session: AsyncSession):
    department = Department(
        department_code="TEST",
        name="Test Department",
        faculty="Faculty of Science & Technology",
    )
    db_session.add(department)
    await db_session.commit()
    await db_session.refresh(department)

    admin_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@aub.edu.kh", "password": "Admin@AUB2026"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    reg_payload = {
        "email": "doc.staff@aub.edu.kh",
        "password": "Password@123",
        "full_name": "Documentation Specialist",
        "student_or_staff_id": "AUB-6093",
        "department_id": department.id,
        "roles": ["Staff"],
    }
    register_res = await client.post(
        "/api/v1/auth/register", json=reg_payload, headers=admin_headers
    )
    assert register_res.status_code == 200

    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": "doc.staff@aub.edu.kh", "password": "Password@123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    sample_file_content = b"Official Policy Document: ACLEDA University Guidelines for FY2026 Academic Research."
    files = {"file": ("research_guidelines_2026.pdf", sample_file_content, "application/pdf")}
    data = {"title": "AUB Research Policy 2026", "academic_year": "2026-2027"}

    upload_res = await client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)
    assert upload_res.status_code == 200
    doc_data = upload_res.json()
    assert doc_data["title"] == "AUB Research Policy 2026"
    assert doc_data["current_version"] == 1
    doc_id = doc_data["id"]

    dup_res = await client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)
    assert dup_res.status_code == 409

    search_res = await client.get("/api/v1/documents/search?q=Research", headers=headers)
    assert search_res.status_code == 200
    assert search_res.json()["total"] >= 1

    meeting_payload = {
        "title": "AUB Faculty Board Review",
        "description": "Evaluation of academic research methodology proposals.",
        "scheduled_start": "2026-11-20T09:00:00",
        "scheduled_end": "2026-11-20T10:30:00",
        "department_id": department.id,
        "agendas": [
            {"item_order": 1, "title": "Opening & Agenda Approval", "duration_minutes": 15},
            {"item_order": 2, "title": "Budget & Resource Allocation", "duration_minutes": 30},
        ],
    }
    meeting_res = await client.post("/api/v1/meetings", json=meeting_payload, headers=headers)
    assert meeting_res.status_code == 200
    meeting_id = meeting_res.json()["id"]

    transcript_text = (
        "Dean Lay Thou: យើងត្រូវ review proposal ទាំងអស់ មុនថ្ងៃ Friday.\n"
        "Khorn Molika: I will submit the ethics approval by 25 November 2026."
    )
    import_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/transcripts/import",
        data={"text": transcript_text},
        headers=headers,
    )
    assert import_res.status_code == 200
    assert import_res.json()["imported"] == 2

    transcripts_res = await client.get(
        f"/api/v1/meetings/{meeting_id}/transcripts", headers=headers
    )
    assert transcripts_res.status_code == 200
    assert len(transcripts_res.json()) == 2
    assert transcripts_res.json()[0]["speaker_label"] == "Dean Lay Thou"

    # No LLM provider is configured for tests: the endpoint must fail honestly.
    synth_res = await client.post(f"/api/v1/meetings/{meeting_id}/synthesize-mom", headers=headers)
    assert synth_res.status_code == 503

    draft_payload = {
        "executive_summary": "The board reviewed the research proposal and confirmed the next steps.",
        "discussion_points": ["Group 4 presented the proposal."],
        "decisions": [
            {
                "agenda_topic": "Research methodology",
                "decision_text": "Approve the proposal for the next stage.",
                "context_notes": None,
            }
        ],
        "action_items": [
            {
                "task_description": "Submit the research ethics approval.",
                "assignee_name": "Khorn Molika",
                "deadline": "2026-11-25",
                "confidence_score": 0.95,
            }
        ],
    }
    draft_res = await client.put(
        f"/api/v1/meetings/{meeting_id}/mom-draft", json=draft_payload, headers=headers
    )
    assert draft_res.status_code == 200
    assert draft_res.json()["is_verified"] is False

    approve_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/approve-mom", json=draft_payload, headers=headers
    )
    assert approve_res.status_code == 200
    summary_data = approve_res.json()
    assert summary_data["is_verified"] is True
    assert len(summary_data["decisions"]) == 1
    assert len(summary_data["action_items"]) == 1

    # The verified minutes are archived in the document repository.
    search_res = await client.get("/api/v1/documents/search?q=Minutes", headers=headers)
    assert search_res.status_code == 200
    archived = search_res.json()["items"]
    assert any(document["drive_file_id"] == meeting_id for document in archived)
    assert any(document["category"]["code"] == "MOM" for document in archived)

    # Re-publishing must not duplicate the archived document.
    again = await client.post(
        f"/api/v1/meetings/{meeting_id}/approve-mom", json=draft_payload, headers=headers
    )
    assert again.status_code == 200
    search_res = await client.get("/api/v1/documents/search?q=Minutes", headers=headers)
    matches = [
        document
        for document in search_res.json()["items"]
        if document["drive_file_id"] == meeting_id
    ]
    assert len(matches) == 1

    # Downloads are generated from the stored minutes.
    docx_res = await client.get(
        f"/api/v1/workspace/meetings/{meeting_id}/minutes.docx", headers=headers
    )
    assert docx_res.status_code == 200
    import io

    import docx

    generated = docx.Document(io.BytesIO(docx_res.content))
    generated_text = "\n".join(paragraph.text for paragraph in generated.paragraphs)
    assert "Attendees" in generated_text
    assert "Opening & Agenda Approval" in generated_text
    assert "Faculty of Science & Technology" in generated_text

    csv_res = await client.get(
        f"/api/v1/workspace/meetings/{meeting_id}/action-items.csv", headers=headers
    )
    assert csv_res.status_code == 200
    assert "Submit the research ethics approval." in csv_res.text

    # Tasks are visible only after verification and can be completed.
    tasks_res = await client.get("/api/v1/tasks/action-items", headers=headers)
    assert tasks_res.status_code == 200
    items = [item for item in tasks_res.json() if item["meeting_id"] == meeting_id]
    assert len(items) == 1
    assert items[0]["is_overdue"] is False
    task_id = items[0]["id"]

    patch_res = await client.patch(
        f"/api/v1/tasks/action-items/{task_id}",
        json={"status": "Completed"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "Completed"

    bad_patch = await client.patch(
        f"/api/v1/tasks/action-items/{task_id}",
        json={"status": "Banana"},
        headers=headers,
    )
    assert bad_patch.status_code == 400

    decisions_res = await client.get("/api/v1/tasks/decisions", headers=headers)
    assert decisions_res.status_code == 200
    assert any(item["meeting_id"] == meeting_id for item in decisions_res.json())

    dashboard_res = await client.get("/api/v1/dashboard", headers=headers)
    assert dashboard_res.status_code == 200
    dashboard = dashboard_res.json()
    assert dashboard["documents_count"] >= 1
    assert dashboard["meetings_count"] >= 1
    assert dashboard["open_action_items_count"] == 0
    assert dashboard["overdue_action_items_count"] == 0
    assert "live_meeting" not in dashboard
