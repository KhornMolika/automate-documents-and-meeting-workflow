from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.meeting import Meeting, MeetingSummary
from app.services.exporter import build_action_items_csv, build_mom_docx

router = APIRouter(prefix="/workspace", tags=["Local exports"])

EXPORT_DIR = Path("./exports")


def _meeting_query(meeting_id: str):
    return (
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(
            selectinload(Meeting.participants),
            selectinload(Meeting.summary).selectinload(MeetingSummary.decisions),
            selectinload(Meeting.summary).selectinload(MeetingSummary.action_items),
        )
    )


@router.post("/meetings/{meeting_id}/export-docs")
async def export_mom_docx(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = (await db.execute(_meeting_query(meeting_id))).scalar_one_or_none()
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=400, detail="Meeting or verified MoM summary not found.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"mom_{meeting.id}.docx"
    path.write_bytes(build_mom_docx(meeting, meeting.summary))

    meeting.summary.mom_doc_id = path.name
    meeting.summary.mom_doc_link = f"/workspace/meetings/{meeting.id}/minutes.docx"
    await db.commit()

    return {
        "status": "success",
        "service": "local-docx",
        "doc_id": path.name,
        "doc_url": meeting.summary.mom_doc_link,
        "template": "ACLEDA University Official MoM Template",
    }


@router.get("/meetings/{meeting_id}/minutes.docx")
async def download_mom_docx(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = (await db.execute(_meeting_query(meeting_id))).scalar_one_or_none()
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Minutes not found.")
    path = EXPORT_DIR / f"mom_{meeting.id}.docx"
    if not path.exists():
        path.write_bytes(build_mom_docx(meeting, meeting.summary))
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{meeting.title.replace(' ', '_')}_minutes.docx",
    )


@router.post("/meetings/{meeting_id}/export-sheets")
async def export_action_items_csv(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = (await db.execute(_meeting_query(meeting_id))).scalar_one_or_none()
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=400, detail="Meeting or verified MoM summary not found.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"action_items_{meeting.id}.csv"
    path.write_text(build_action_items_csv(meeting, meeting.summary), encoding="utf-8")

    for index, item in enumerate(meeting.summary.action_items, start=2):
        item.sheets_row_index = index
    await db.commit()

    return {
        "status": "success",
        "service": "local-csv",
        "spreadsheet_id": path.name,
        "spreadsheet_url": f"/workspace/meetings/{meeting.id}/action-items.csv",
        "rows_appended": len(meeting.summary.action_items),
    }


@router.get("/meetings/{meeting_id}/action-items.csv")
async def download_action_items_csv(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = (await db.execute(_meeting_query(meeting_id))).scalar_one_or_none()
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Action items not found.")
    path = EXPORT_DIR / f"action_items_{meeting.id}.csv"
    if not path.exists():
        path.write_text(build_action_items_csv(meeting, meeting.summary), encoding="utf-8")
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"{meeting.title.replace(' ', '_')}_action_items.csv",
    )


@router.post("/meetings/{meeting_id}/send-gmail")
async def send_gmail_notice(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    raise HTTPException(
        status_code=503,
        detail="Gmail delivery is not configured for this deployment. Verify or download the minutes instead.",
    )
