from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.document import Document, DocumentPermission
from app.models.meeting import ActionItem, Meeting, MeetingSummary
from app.models.user import User
from app.schemas.document import DocumentOut

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _meeting_options():
    return (
        selectinload(Meeting.agendas),
        selectinload(Meeting.participants),
        selectinload(Meeting.summary),
    )


def serialize_meeting(meeting: Meeting) -> dict[str, Any]:
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

    action_stmt = (
        select(ActionItem, Meeting.id, Meeting.title, Meeting.scheduled_start)
        .join(MeetingSummary, ActionItem.summary_id == MeetingSummary.id)
        .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
        .where(
            MeetingSummary.is_verified.is_(True),
            ActionItem.status != "Completed",
        )
    )
    if department_id:
        action_stmt = action_stmt.where(Meeting.department_id == department_id)
    action_stmt = action_stmt.order_by(
        ActionItem.deadline.asc().nulls_last(),
        ActionItem.created_at.asc(),
    )
    action_rows = (await db.execute(action_stmt)).all()

    today = date.today()
    action_items = []
    for item, meeting_id, meeting_title, meeting_date in action_rows:
        is_overdue = bool(item.deadline and item.deadline < today)
        action_items.append(
            {
                "id": item.id,
                "task": item.task_description,
                "assignee": item.raw_assignee_name,
                "deadline": item.deadline.isoformat() if item.deadline else None,
                "status": item.status,
                "is_overdue": is_overdue,
                "meeting_id": meeting_id,
                "meeting_title": meeting_title,
                "meeting_date": meeting_date.isoformat(),
            }
        )

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
        .options(
            selectinload(Document.category),
            selectinload(Document.folder),
            selectinload(Document.versions),
            selectinload(Document.permissions).selectinload(DocumentPermission.user),
        )
    )
    recent_documents = (await db.execute(recent_doc_stmt)).scalars().all()
    recent_documents = [
        document
        for document in recent_documents
        if (
            current_user.is_superuser
            or document.owner_id == current_user.id
            or not document.is_restricted
            or any(item.user_id == current_user.id for item in document.permissions)
        )
    ]
    for document in recent_documents:
        if document.versions:
            document.latest_version = document.versions[0]

    return {
        "documents_count": documents_count or 0,
        "meetings_count": meetings_count or 0,
        "open_action_items_count": len(action_items),
        "overdue_action_items_count": sum(1 for item in action_items if item["is_overdue"]),
        "next_meeting": serialize_meeting(next_meeting) if next_meeting else None,
        "recent_documents": [
            DocumentOut.model_validate(document).model_dump(mode="json")
            for document in recent_documents
        ],
        "action_items": action_items[:6],
    }
