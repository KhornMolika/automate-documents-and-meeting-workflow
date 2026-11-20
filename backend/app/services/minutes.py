"""Verified-minutes exports and repository archiving."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentCategory, DocumentVersion
from app.models.meeting import Meeting, MeetingSummary
from app.services.exporter import build_action_items_csv, build_mom_docx

EXPORT_DIR = Path("./exports")
MOM_CATEGORY_CODE = "MOM"


def _academic_year(value: datetime) -> str:
    start = value.year if value.month >= 9 else value.year - 1
    return f"{start}-{start + 1}"


def _minutes_text(summary: MeetingSummary) -> str:
    parts = [summary.executive_summary]
    try:
        import json

        points = json.loads(summary.discussion_highlights or "[]")
        if isinstance(points, list):
            parts.extend(str(point) for point in points)
    except Exception:
        pass
    parts.extend(decision.decision_text for decision in summary.decisions)
    parts.extend(
        f"{item.task_description} {item.raw_assignee_name or ''}" for item in summary.action_items
    )
    return "\n".join(part for part in parts if part).strip()


async def _mom_category(db: AsyncSession) -> DocumentCategory:
    stmt = select(DocumentCategory).where(DocumentCategory.code == MOM_CATEGORY_CODE)
    category = (await db.execute(stmt)).scalar_one_or_none()
    if category:
        return category
    category = DocumentCategory(
        code=MOM_CATEGORY_CODE,
        name="Minutes of Meeting",
        description="Official recorded minutes",
    )
    db.add(category)
    await db.flush()
    return category


async def export_verified_minutes(
    db: AsyncSession,
    meeting: Meeting,
    summary: MeetingSummary,
) -> dict[str, Any]:
    """Write DOCX/CSV files and upsert the verified minutes into Documents."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    docx_bytes = build_mom_docx(meeting, summary)
    docx_path = EXPORT_DIR / f"mom_{meeting.id}.docx"
    docx_path.write_bytes(docx_bytes)

    csv_text = build_action_items_csv(meeting, summary)
    csv_path = EXPORT_DIR / f"action_items_{meeting.id}.csv"
    csv_path.write_text(csv_text, encoding="utf-8")

    category = await _mom_category(db)
    stmt = select(Document).where(
        Document.drive_file_id == meeting.id,
        Document.category_id == category.id,
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    title = f"Minutes of Meeting — {meeting.title}"
    academic_year = _academic_year(meeting.scheduled_start)
    owner_id = summary.verified_by or meeting.created_by
    checksum = hashlib.sha256(docx_bytes).hexdigest()

    if not document:
        document = Document(
            title=title,
            category_id=category.id,
            department_id=meeting.department_id,
            owner_id=owner_id,
            academic_year=academic_year,
            current_version=1,
            drive_file_id=meeting.id,
            drive_web_link=f"/meetings/{meeting.id}/review",
        )
        db.add(document)
        await db.flush()
    else:
        document.title = title
        document.department_id = meeting.department_id
        document.academic_year = academic_year
        document.drive_web_link = f"/meetings/{meeting.id}/review"
        document.is_archived = False

    version_stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document.id,
        DocumentVersion.version_number == 1,
    )
    version = (await db.execute(version_stmt)).scalar_one_or_none()
    extracted_text = _minutes_text(summary)
    if not version:
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            file_name=docx_path.name,
            file_path=str(docx_path),
            file_size_bytes=len(docx_bytes),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            sha256_checksum=checksum,
            extracted_text=extracted_text,
            abstract_summary=summary.executive_summary,
            uploaded_by=owner_id,
        )
        db.add(version)
    else:
        version.file_name = docx_path.name
        version.file_path = str(docx_path)
        version.file_size_bytes = len(docx_bytes)
        version.sha256_checksum = checksum
        version.extracted_text = extracted_text
        version.abstract_summary = summary.executive_summary
        version.uploaded_by = owner_id

    summary.mom_doc_id = docx_path.name
    summary.mom_doc_link = f"/workspace/meetings/{meeting.id}/minutes.docx"

    return {
        "docx_path": docx_path,
        "csv_path": csv_path,
        "document_id": document.id,
        "title": title,
    }
