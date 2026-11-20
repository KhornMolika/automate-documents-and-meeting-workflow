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
    reg_payload = {
        "email": "test.staff@aub.edu.kh",
        "password": "Password@123",
        "full_name": "Test Academic Staff",
        "student_or_staff_id": "AUB-5801",
        "roles": ["Staff"],
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    assert reg_res.json()["email"] == "test.staff@aub.edu.kh"

    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": "test.staff@aub.edu.kh", "password": "Password@123"},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "test.staff@aub.edu.kh"


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

    reg_payload = {
        "email": "doc.staff@aub.edu.kh",
        "password": "Password@123",
        "full_name": "Documentation Specialist",
        "student_or_staff_id": "AUB-6093",
        "department_id": department.id,
        "roles": ["Staff"],
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

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

    segment_payload = {
        "speaker_label": "Dean Lay Thou",
        "start_timestamp": 12.5,
        "end_timestamp": 18.0,
        "original_text": "យើងត្រូវ review proposal ទាំងអស់ មុនថ្ងៃ Friday.",
        "translated_text": "We need to review all proposals before Friday.",
        "confidence_score": 0.97,
        "language_detected": "km-en",
    }
    trans_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/transcripts", json=segment_payload, headers=headers
    )
    assert trans_res.status_code == 200

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

    approve_payload = {
        **draft_payload,
        "export_to_google_docs": False,
        "export_to_google_sheets": False,
    }
    approve_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/approve-mom", json=approve_payload, headers=headers
    )
    assert approve_res.status_code == 200
    summary_data = approve_res.json()
    assert summary_data["is_verified"] is True
    assert len(summary_data["decisions"]) == 1
    assert len(summary_data["action_items"]) == 1

    docs_res = await client.post(
        f"/api/v1/workspace/meetings/{meeting_id}/export-docs", headers=headers
    )
    assert docs_res.status_code == 200
    assert docs_res.json()["service"] == "local-docx"
    assert docs_res.json()["doc_url"].endswith("/minutes.docx")

    sheets_res = await client.post(
        f"/api/v1/workspace/meetings/{meeting_id}/export-sheets", headers=headers
    )
    assert sheets_res.status_code == 200
    assert sheets_res.json()["rows_appended"] == 1

    # Start/end lifecycle and dashboard aggregation.
    start_res = await client.post(f"/api/v1/meetings/{meeting_id}/start", headers=headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "In Progress"

    dashboard_res = await client.get("/api/v1/dashboard", headers=headers)
    assert dashboard_res.status_code == 200
    dashboard = dashboard_res.json()
    assert dashboard["documents_count"] >= 1
    assert dashboard["meetings_count"] >= 1
    assert dashboard["live_meeting"]["id"] == meeting_id
    assert any(item["meeting_id"] == meeting_id for item in dashboard["action_items"])
    assert any(item["meeting_id"] == meeting_id for item in dashboard["recent_decisions"])

    end_res = await client.post(f"/api/v1/meetings/{meeting_id}/end", headers=headers)
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "Completed"
