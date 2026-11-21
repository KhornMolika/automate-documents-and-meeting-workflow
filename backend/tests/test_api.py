import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Department, User


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
async def test_document_and_meeting_lifecycle(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
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
    assert doc_data["latest_version"]["contains_khmer"] is False
    doc_id = doc_data["id"]

    bad_summary = await client.post(
        f"/api/v1/documents/{doc_id}/summarize?language=fr", headers=headers
    )
    assert bad_summary.status_code == 422

    khmer_csv = "ចំណងជើង,អ្នកទទួល\nសាកល្បង,នាយកដ្ឋាន\n".encode("utf-8")
    khmer_upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("khmer_policy.csv", khmer_csv, "text/csv")},
        data={"title": "Khmer Policy", "academic_year": "2026-2027"},
        headers=headers,
    )
    assert khmer_upload.status_code == 200
    assert khmer_upload.json()["latest_version"]["contains_khmer"] is True

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
    synth_km_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/synthesize-mom?language=km",
        headers=headers,
    )
    assert synth_km_res.status_code == 503
    bad_language_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/synthesize-mom?language=fr",
        headers=headers,
    )
    assert bad_language_res.status_code == 422

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
    assert summary_data["drive_files"] == []

    async def fake_drive_publish(meeting, summary):
        return [
            {
                "id": "drive-doc-1",
                "name": f"{meeting.title}_minutes.docx",
                "webViewLink": "https://drive.google.com/file/d/drive-doc-1/view",
            }
        ]

    monkeypatch.setattr(
        "app.services.google_drive.GoogleDriveService.is_configured",
        property(lambda self: True),
    )
    monkeypatch.setattr(
        "app.api.v1.meetings.google_drive.publish_minutes", fake_drive_publish
    )
    drive_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/approve-mom",
        json={**draft_payload, "publish_to_drive": True},
        headers=headers,
    )
    assert drive_res.status_code == 200
    assert drive_res.json()["drive_files"][0]["id"] == "drive-doc-1"

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

    page_res = await client.get(
        "/api/v1/meetings?page=1&page_size=10&view=published", headers=headers
    )
    assert page_res.status_code == 200
    page_data = page_res.json()
    assert page_data["items"][0]["id"] == meeting_id
    assert page_data["total"] == 1
    assert page_data["counts"]["published"] == 1
    assert page_data["pages"] == 1

    rename_res = await client.patch(
        f"/api/v1/meetings/{meeting_id}",
        json={"title": "Renamed Faculty Board Review"},
        headers=headers,
    )
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Renamed Faculty Board Review"

    delete_res = await client.delete(f"/api/v1/meetings/{meeting_id}", headers=headers)
    assert delete_res.status_code == 204
    missing_res = await client.get(f"/api/v1/meetings/{meeting_id}", headers=headers)
    assert missing_res.status_code == 404

    search_after_delete = await client.get("/api/v1/documents/search?q=Minutes", headers=headers)
    assert all(
        document["drive_file_id"] != meeting_id
        for document in search_after_delete.json()["items"]
    )

    # Document actions: download, rename, version, archive/restore and delete.
    download_res = await client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert download_res.status_code == 200
    assert download_res.content == sample_file_content

    version_res = await client.post(
        f"/api/v1/documents/{doc_id}/versions",
        files={"file": ("policy_v2.csv", b"Policy,Owner\nUpdated,Academic Affairs\n", "text/csv")},
        headers=headers,
    )
    assert version_res.status_code == 200
    assert version_res.json()["current_version"] == 2
    assert len(version_res.json()["versions"]) == 2

    rename_doc = await client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"title": "Renamed Research Policy"},
        headers=headers,
    )
    assert rename_doc.status_code == 200
    assert rename_doc.json()["title"] == "Renamed Research Policy"

    archive_doc = await client.patch(
        f"/api/v1/documents/{doc_id}/archive",
        json={"is_archived": True},
        headers=headers,
    )
    assert archive_doc.status_code == 200
    assert archive_doc.json()["is_archived"] is True
    active_docs = await client.get("/api/v1/documents?limit=200", headers=headers)
    assert all(item["id"] != doc_id for item in active_docs.json())
    archived_docs = await client.get(
        "/api/v1/documents?limit=200&include_archived=true", headers=headers
    )
    assert any(item["id"] == doc_id for item in archived_docs.json())

    restore_doc = await client.patch(
        f"/api/v1/documents/{doc_id}/archive",
        json={"is_archived": False},
        headers=headers,
    )
    assert restore_doc.status_code == 200
    assert restore_doc.json()["is_archived"] is False

    delete_doc = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert delete_doc.status_code == 204
    missing_doc = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert missing_doc.status_code == 404


@pytest.mark.asyncio
async def test_document_folders_access_and_versions(client: AsyncClient, db_session: AsyncSession):
    department = Department(
        department_code="ORG",
        name="Organisation Department",
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
    for email, name in [
        ("owner@aub.edu.kh", "Folder Owner"),
        ("viewer@aub.edu.kh", "Folder Viewer"),
    ]:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password@123",
                "full_name": name,
                "department_id": department.id,
                "roles": ["Staff"],
            },
            headers=admin_headers,
        )
        assert reg.status_code == 200

    owner_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "owner@aub.edu.kh", "password": "Password@123"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
    viewer_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "viewer@aub.edu.kh", "password": "Password@123"},
    )
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}
    viewer_id = (
        await db_session.execute(select(User).where(User.email == "viewer@aub.edu.kh"))
    ).scalar_one().id

    folder = await client.post(
        "/api/v1/documents/folders",
        json={"name": "Policies"},
        headers=owner_headers,
    )
    assert folder.status_code == 200
    folder_id = folder.json()["id"]

    upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("folder-policy.csv", b"Policy,Owner\nDemo,Academic Affairs\n", "text/csv")},
        data={"title": "Folder Policy", "folder_id": folder_id},
        headers=owner_headers,
    )
    assert upload.status_code == 200
    document_id = upload.json()["id"]
    assert upload.json()["folder_id"] == folder_id
    version_id = upload.json()["latest_version"]["id"]

    folders = await client.get("/api/v1/documents/folders", headers=owner_headers)
    assert folders.status_code == 200
    assert folders.json()[0]["document_count"] == 1

    move_root = await client.patch(
        f"/api/v1/documents/{document_id}",
        json={"folder_id": None},
        headers=owner_headers,
    )
    assert move_root.status_code == 200
    assert move_root.json()["folder_id"] is None

    move_back = await client.patch(
        f"/api/v1/documents/{document_id}",
        json={"folder_id": folder_id},
        headers=owner_headers,
    )
    assert move_back.status_code == 200
    assert move_back.json()["folder_id"] == folder_id

    restrict = await client.patch(
        f"/api/v1/documents/{document_id}",
        json={"is_restricted": True},
        headers=owner_headers,
    )
    assert restrict.status_code == 200
    viewer_before = await client.get(
        f"/api/v1/documents/{document_id}", headers=viewer_headers
    )
    assert viewer_before.status_code == 403

    share = await client.post(
        f"/api/v1/documents/{document_id}/permissions",
        json={"user_id": viewer_id, "permission": "view"},
        headers=owner_headers,
    )
    assert share.status_code == 200
    assert share.json()["permissions"][0]["full_name"] == "Folder Viewer"
    viewer_after = await client.get(
        f"/api/v1/documents/{document_id}", headers=viewer_headers
    )
    assert viewer_after.status_code == 200

    remove_share = await client.delete(
        f"/api/v1/documents/{document_id}/permissions/{viewer_id}",
        headers=owner_headers,
    )
    assert remove_share.status_code == 204
    viewer_removed = await client.get(
        f"/api/v1/documents/{document_id}", headers=viewer_headers
    )
    assert viewer_removed.status_code == 403

    version = await client.post(
        f"/api/v1/documents/{document_id}/versions",
        files={"file": ("folder-policy-v2.csv", b"Policy,Owner\nUpdated,Academic Affairs\n", "text/csv")},
        headers=owner_headers,
    )
    assert version.status_code == 200
    restore = await client.post(
        f"/api/v1/documents/{document_id}/versions/{version_id}/restore",
        headers=owner_headers,
    )
    assert restore.status_code == 200
    assert restore.json()["current_version"] == 3

    folder_delete = await client.delete(
        f"/api/v1/documents/folders/{folder_id}", headers=owner_headers
    )
    assert folder_delete.status_code == 204
    moved = await client.get(f"/api/v1/documents/{document_id}", headers=owner_headers)
    assert moved.json()["folder_id"] is None

    users = await client.get("/api/v1/auth/users", headers=admin_headers)
    assert users.status_code == 200
    assert any(user["email"] == "viewer@aub.edu.kh" for user in users.json())
    deactivate = await client.patch(
        f"/api/v1/auth/users/{viewer_id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert deactivate.status_code == 200
    inactive_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "viewer@aub.edu.kh", "password": "Password@123"},
    )
    assert inactive_login.status_code == 403


@pytest.mark.asyncio
async def test_semantic_document_search(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    department = Department(
        department_code="SEM",
        name="Semantic Department",
        faculty="Faculty of Science & Technology",
    )
    db_session.add(department)
    await db_session.commit()
    await db_session.refresh(department)
    admin_user = (
        await db_session.execute(select(User).where(User.email == "admin@aub.edu.kh"))
    ).scalar_one()
    admin_user.department_id = department.id
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@aub.edu.kh", "password": "Admin@AUB2026"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    async def fake_embed(text: str):
        return [0.0, 1.0] if "beta" in text.lower() else [1.0, 0.0]

    monkeypatch.setattr("app.api.v1.documents.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.api.v1.documents.llm_service.embed_text", fake_embed)

    for title, content in [
        ("Alpha Policy", b"Policy,Owner\nAlpha,Academic Affairs\n"),
        ("Beta Policy", b"Policy,Owner\nBeta,Academic Affairs\n"),
    ]:
        upload = await client.post(
            "/api/v1/documents/upload",
            files={"file": (f"{title}.csv", content, "text/csv")},
            data={"title": title},
            headers=headers,
        )
        assert upload.status_code == 200

    semantic = await client.get(
        "/api/v1/documents/search?q=concept&semantic=true", headers=headers
    )
    assert semantic.status_code == 200
    assert semantic.json()["total"] == 1
    assert semantic.json()["items"][0]["title"] == "Alpha Policy"


@pytest.mark.asyncio
async def test_google_document_import(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    department = Department(
        department_code="GDRIVE",
        name="Google Import Department",
        faculty="Faculty of Science & Technology",
    )
    db_session.add(department)
    await db_session.commit()
    await db_session.refresh(department)
    admin_user = (
        await db_session.execute(select(User).where(User.email == "admin@aub.edu.kh"))
    ).scalar_one()
    admin_user.department_id = department.id
    await db_session.commit()

    admin_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@aub.edu.kh", "password": "Admin@AUB2026"},
    )
    headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    class FakeResponse:
        status_code = 200
        headers = {
            "content-type": "text/csv",
            "content-disposition": 'attachment; filename="imported-sheet.csv"',
        }

        async def aiter_bytes(self):
            yield b"Policy,Owner\nImported Google Sheet,Academic Affairs\n"

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *args):
            return False

    requested_urls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, method, url):
            requested_urls.append(url)
            return FakeStream()

    monkeypatch.setattr("app.api.v1.documents.httpx.AsyncClient", FakeClient)

    import_res = await client.post(
        "/api/v1/documents/import/google",
        json={
            "url": "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0",
            "title": "Imported Google Sheet",
            "academic_year": "2026-2027",
        },
        headers=headers,
    )
    assert import_res.status_code == 200, import_res.text
    imported = import_res.json()
    assert imported["title"] == "Imported Google Sheet"
    assert imported["latest_version"]["file_name"] == "imported-sheet.csv"
    assert "spreadsheets/d/abc123/export?format=xlsx" in requested_urls[0]
    search_imported = await client.get(
        "/api/v1/documents/search?q=Imported%20Google%20Sheet", headers=headers
    )
    assert search_imported.status_code == 200
    assert any(item["id"] == imported["id"] for item in search_imported.json()["items"])

    invalid_res = await client.post(
        "/api/v1/documents/import/google",
        json={"url": "https://example.com/not-google"},
        headers=headers,
    )
    assert invalid_res.status_code == 400
