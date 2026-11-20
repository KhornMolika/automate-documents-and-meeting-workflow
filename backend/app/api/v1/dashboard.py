from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.document import Document
from app.models.meeting import ActionItem, Decision, Meeting, MeetingSummary
from app.models.user import User
from app.schemas.document import DocumentOut

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _meeting_options():
    return (
        selectinload(Meeting.agendas),
        selectinload(Meeting.participants),
        selectinload(Meeting.transcripts),
        selectinload(Meeting.summary).selectinload(MeetingSummary.decisions),
        selectinload(Meeting.summary).selectinload(MeetingSummary.action_items),
    )


def serialize_meeting(meeting: Meeting) -> dict[str, Any]:
    summary = meeting.summary
    return {
        "id": meeting.id,
        "title": meeting.title,
        "status": meeting.status,
        "scheduled_start": meeting.scheduled_start.isoformat(),
        "scheduled_end": meeting.scheduled_end.isoformat(),
        "participants": meeting.participant_count,
        "agenda": [
            {"title": item.title, "duration_minutes": item.duration_minutes}
            for item in meeting.agendas
        ],
        "transcript_count": len(meeting.transcripts),
        "summary": (
            {
                "id": summary.id,
                "is_verified": summary.is_verified,
                "decisions_count": len(summary.decisions),
                "action_items_count": len(summary.action_items),
            }
            if summary
            else None
        ),
    }


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    department_id = current_user.department_id
    now = datetime.utcnow()

    document_stmt = select(Document).where(Document.is_archived.is_(False))
    meeting_stmt = select(Meeting)
    if department_id:
        document_stmt = document_stmt.where(Document.department_id == department_id)
        meeting_stmt = meeting_stmt.where(Meeting.department_id == department_id)

    documents_count = await db.scalar(
        select(func.count()).select_from(document_stmt.subquery())
    )
    meetings_count = await db.scalar(
        select(func.count()).select_from(meeting_stmt.subquery())
    )

    open_action_stmt = (
        select(ActionItem, Meeting.id, Meeting.title)
        .join(MeetingSummary, ActionItem.summary_id == MeetingSummary.id)
        .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
        .where(ActionItem.status != "Completed")
    )
    if department_id:
        open_action_stmt = open_action_stmt.where(Meeting.department_id == department_id)
    open_action_stmt = open_action_stmt.order_by(ActionItem.deadline.asc().nulls_last())
    open_action_rows = (await db.execute(open_action_stmt)).all()

    open_action_items = [
        {
            "id": item.id,
            "task": item.task_description,
            "assignee": item.raw_assignee_name,
            "deadline": item.deadline.isoformat() if item.deadline else None,
            "status": item.status,
            "meeting_id": meeting_id,
            "meeting_title": meeting_title,
        }
        for item, meeting_id, meeting_title in open_action_rows
    ]

    decision_stmt = (
        select(Decision, Meeting.id, Meeting.title, MeetingSummary.verified_at, Meeting.scheduled_start)
        .join(MeetingSummary, Decision.summary_id == MeetingSummary.id)
        .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
        .where(MeetingSummary.is_verified.is_(True))
    )
    if department_id:
        decision_stmt = decision_stmt.where(Meeting.department_id == department_id)
    decision_stmt = decision_stmt.order_by(
        MeetingSummary.verified_at.desc(), Meeting.scheduled_start.desc()
    ).limit(6)
    decision_rows = (await db.execute(decision_stmt)).all()

    recent_decisions = [
        {
            "id": decision.id,
            "text": decision.decision_text,
            "agenda_topic": decision.agenda_topic,
            "meeting_id": meeting_id,
            "meeting_title": meeting_title,
            "date": (verified_at or scheduled_start).isoformat(),
        }
        for decision, meeting_id, meeting_title, verified_at, scheduled_start in decision_rows
    ]

    live_meeting = None
    live_stmt = meeting_stmt.where(Meeting.status == "In Progress").order_by(
        Meeting.scheduled_start.asc()
    ).limit(1).options(*_meeting_options())
    live_meeting = (await db.execute(live_stmt)).scalar_one_or_none()

    next_meeting = None
    next_stmt = (
        meeting_stmt.where(Meeting.status == "Scheduled", Meeting.scheduled_start >= now)
        .order_by(Meeting.scheduled_start.asc())
        .limit(1)
        .options(*_meeting_options())
    )
    next_meeting = (await db.execute(next_stmt)).scalar_one_or_none()

    recent_doc_stmt = (
        document_stmt.order_by(Document.created_at.desc())
        .limit(5)
        .options(selectinload(Document.category), selectinload(Document.versions))
    )
    recent_documents = (await db.execute(recent_doc_stmt)).scalars().all()
    for document in recent_documents:
        if document.versions:
            document.latest_version = document.versions[0]

    turnaround_stmt = (
        select(MeetingSummary.verified_at, Meeting.scheduled_end)
        .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
        .where(
            MeetingSummary.is_verified.is_(True),
            MeetingSummary.verified_at.is_not(None),
            Meeting.scheduled_end <= MeetingSummary.verified_at,
        )
    )
    if department_id:
        turnaround_stmt = turnaround_stmt.where(Meeting.department_id == department_id)
    turnaround_rows = await db.execute(turnaround_stmt)
    durations = [
        (verified_at - scheduled_end).total_seconds() / 60
        for verified_at, scheduled_end in turnaround_rows.all()
    ]
    mom_turnaround = round(sum(durations) / len(durations), 1) if durations else None

    return {
        "documents_count": documents_count or 0,
        "meetings_count": meetings_count or 0,
        "open_action_items_count": len(open_action_items),
        "mom_turnaround_minutes": mom_turnaround,
        "live_meeting": serialize_meeting(live_meeting) if live_meeting else None,
        "next_meeting": serialize_meeting(next_meeting) if next_meeting else None,
        "recent_documents": [
            DocumentOut.model_validate(document).model_dump(mode="json")
            for document in recent_documents
        ],
        "action_items": open_action_items,
        "recent_decisions": recent_decisions,
    }
