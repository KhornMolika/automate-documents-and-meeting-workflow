from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.meeting import Meeting, MeetingParticipant, MeetingSummary
from app.models.user import User
from app.services.exporter import build_action_items_csv, build_mom_docx

router = APIRouter(prefix="/workspace", tags=["Local exports"])

EXPORT_DIR = Path("./exports")


def _meeting_query(meeting_id: str):
    return (
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(
            selectinload(Meeting.agendas),
            selectinload(Meeting.participants).selectinload(MeetingParticipant.user),
            selectinload(Meeting.department),
            selectinload(Meeting.summary).selectinload(MeetingSummary.decisions),
            selectinload(Meeting.summary).selectinload(MeetingSummary.action_items),
        )
    )


@router.get("/meetings/{meeting_id}/minutes.docx")
async def download_mom_docx(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = (await db.execute(_meeting_query(meeting_id))).scalar_one_or_none()
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Minutes not found.")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"mom_{meeting.id}.docx"
    if not path.exists():
        path.write_bytes(build_mom_docx(meeting, meeting.summary))
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{meeting.title.replace(' ', '_')}_minutes.docx",
    )


@router.get("/meetings/{meeting_id}/action-items.csv")
async def download_action_items_csv(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = (await db.execute(_meeting_query(meeting_id))).scalar_one_or_none()
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Action items not found.")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"action_items_{meeting.id}.csv"
    if not path.exists():
        path.write_text(build_action_items_csv(meeting, meeting.summary), encoding="utf-8")
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"{meeting.title.replace(' ', '_')}_action_items.csv",
    )
