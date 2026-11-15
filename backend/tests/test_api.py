import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ACLEDA" in data["app"]


@pytest.mark.asyncio
async def test_auth_workflow(client: AsyncClient):
    # 1. Register a test staff member
    reg_payload = {
        "email": "test.staff@aub.edu.kh",
        "password": "Password@123",
        "full_name": "Test Academic Staff",
        "student_or_staff_id": "AUB-5801",
        "roles": ["Staff"]
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    user_data = reg_res.json()
    assert user_data["email"] == "test.staff@aub.edu.kh"

    # 2. Login to get JWT
    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": "test.staff@aub.edu.kh", "password": "Password@123"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    access_token = token_data["access_token"]

    # 3. Access protected /me route
    headers = {"Authorization": f"Bearer {access_token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "test.staff@aub.edu.kh"


@pytest.mark.asyncio
async def test_document_and_meeting_lifecycle(client: AsyncClient):
    # 0. Register user for this test session
    reg_payload = {
        "email": "doc.staff@aub.edu.kh",
        "password": "Password@123",
        "full_name": "Documentation Specialist",
        "student_or_staff_id": "AUB-6093",
        "roles": ["Staff"]
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # 1. Authenticate
    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": "doc.staff@aub.edu.kh", "password": "Password@123"}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload Document
    sample_file_content = b"Official Policy Document: ACLEDA University Guidelines for FY2026 Academic Research."
    files = {"file": ("research_guidelines_2026.pdf", sample_file_content, "application/pdf")}
    data = {"title": "AUB Research Policy 2026", "academic_year": "2026-2027"}

    upload_res = await client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)
    assert upload_res.status_code == 200
    doc_data = upload_res.json()
    assert doc_data["title"] == "AUB Research Policy 2026"
    assert doc_data["current_version"] == 1
    doc_id = doc_data["id"]

    # Test duplicate detection
    dup_res = await client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)
    assert dup_res.status_code == 409 # Duplicate rejected!

    # 2. Search Document
    search_res = await client.get("/api/v1/documents/search?q=Research", headers=headers)
    assert search_res.status_code == 200
    search_json = search_res.json()
    assert search_json["total"] >= 1
    assert search_json["query_latency_ms"] >= 0

    # 3. Create Meeting
    meeting_payload = {
        "title": "AUB Faculty Board Review",
        "description": "Evaluation of academic research methodology proposals.",
        "scheduled_start": "2026-11-20T09:00:00",
        "scheduled_end": "2026-11-20T10:30:00",
        "department_id": "CS",
        "agendas": [
            {"item_order": 1, "title": "Opening & Agenda Approval", "duration_minutes": 15},
            {"item_order": 2, "title": "Budget & Resource Allocation", "duration_minutes": 30}
        ]
    }
    meeting_res = await client.post("/api/v1/meetings", json=meeting_payload, headers=headers)
    assert meeting_res.status_code == 200
    meeting_data = meeting_res.json()
    meeting_id = meeting_data["id"]

    # 4. Ingest Transcript Segment
    segment_payload = {
        "speaker_label": "Dean Lay Thou",
        "start_timestamp": 12.5,
        "end_timestamp": 18.0,
        "original_text": "យើងត្រូវ review proposal ទាំងអស់ មុនថ្ងៃ Friday.",
        "translated_text": "We need to review all proposals before Friday.",
        "confidence_score": 0.97,
        "language_detected": "km-en"
    }
    trans_res = await client.post(f"/api/v1/meetings/{meeting_id}/transcripts", json=segment_payload, headers=headers)
    assert trans_res.status_code == 200

    # 5. Synthesize MoM via Gemini
    synth_res = await client.post(f"/api/v1/meetings/{meeting_id}/synthesize-mom", headers=headers)
    assert synth_res.status_code == 200
    synth_json = synth_res.json()
    assert "executive_summary" in synth_json
    assert len(synth_json["decisions"]) >= 1
    assert len(synth_json["action_items"]) >= 1

    # 6. Human-in-the-Loop Review & Approval
    approval_payload = {
        "executive_summary": synth_json["executive_summary"],
        "discussion_points": synth_json["discussion_points"],
        "decisions": synth_json["decisions"],
        "action_items": synth_json["action_items"],
        "export_to_google_docs": True,
        "export_to_google_sheets": True
    }
    approve_res = await client.post(f"/api/v1/meetings/{meeting_id}/approve-mom", json=approval_payload, headers=headers)
    assert approve_res.status_code == 200
    summary_data = approve_res.json()
    assert summary_data["is_verified"] is True

    # 7. Google Workspace Export
    docs_res = await client.post(f"/api/v1/workspace/meetings/{meeting_id}/export-docs", headers=headers)
    assert docs_res.status_code == 200
    assert "https://docs.google.com" in docs_res.json()["doc_url"]

    sheets_res = await client.post(f"/api/v1/workspace/meetings/{meeting_id}/export-sheets", headers=headers)
    assert sheets_res.status_code == 200
    assert sheets_res.json()["rows_appended"] >= 1
