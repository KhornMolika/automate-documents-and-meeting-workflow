from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.meeting import ActionItem, Decision, Meeting, MeetingSummary
from app.models.user import User
from app.schemas.task import (
    ACTION_ITEM_STATUSES,
    ActionItemStatusUpdate,
    ActionItemTrackerOut,
    DecisionTrackerOut,
)

router = APIRouter(prefix="/tasks", tags=["Follow-ups"])


def _department_scope(stmt, current_user: User):
    if current_user.department_id:
        return stmt.where(Meeting.department_id == current_user.department_id)
    return stmt


def _action_item_row(item: ActionItem, meeting: Meeting) -> ActionItemTrackerOut:
    is_overdue = bool(
        item.deadline
        and item.deadline < date.today()
        and item.status != "Completed"
    )
    return ActionItemTrackerOut(
        id=item.id,
        meeting_id=meeting.id,
        meeting_title=meeting.title,
        meeting_date=meeting.scheduled_start,
        task_description=item.task_description,
        assignee_name=item.raw_assignee_name,
        deadline=item.deadline,
        status=item.status,
        is_overdue=is_overdue,
        created_at=item.created_at,
    )


@router.get("/action-items", response_model=List[ActionItemTrackerOut])
async def list_action_items(
    status: Optional[str] = Query(None),
    overdue: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if status and status not in ACTION_ITEM_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown action item status.")

    stmt = (
        select(ActionItem, Meeting)
        .join(MeetingSummary, ActionItem.summary_id == MeetingSummary.id)
        .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
        .where(MeetingSummary.is_verified.is_(True))
        .order_by(ActionItem.deadline.asc().nulls_last(), ActionItem.created_at.asc())
    )
    stmt = _department_scope(stmt, current_user)
    if status:
        stmt = stmt.where(ActionItem.status == status)

    rows = (await db.execute(stmt)).all()
    items = [_action_item_row(item, meeting) for item, meeting in rows]
    if overdue is not None:
        items = [item for item in items if item.is_overdue is overdue]
    return items


@router.patch("/action-items/{item_id}", response_model=ActionItemTrackerOut)
async def update_action_item_status(
    item_id: str,
    payload: ActionItemStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if payload.status not in ACTION_ITEM_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(ACTION_ITEM_STATUSES)}.",
        )

    stmt = (
        select(ActionItem, Meeting)
        .join(MeetingSummary, ActionItem.summary_id == MeetingSummary.id)
        .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
        .where(ActionItem.id == item_id, MeetingSummary.is_verified.is_(True))
    )
    stmt = _department_scope(stmt, current_user)
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Action item not found.")

    item, meeting = row
    item.status = payload.status
    await db.commit()
    await db.refresh(item)
    return _action_item_row(item, meeting)


@router.get("/decisions", response_model=List[DecisionTrackerOut])
async def list_decisions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Decision, Meeting)
        .join(MeetingSummary, Decision.summary_id == MeetingSummary.id)
        .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
        .where(MeetingSummary.is_verified.is_(True))
        .order_by(MeetingSummary.verified_at.desc(), Meeting.scheduled_start.desc())
    )
    stmt = _department_scope(stmt, current_user)
    rows = (await db.execute(stmt)).all()
    return [
        DecisionTrackerOut(
            id=decision.id,
            meeting_id=meeting.id,
            meeting_title=meeting.title,
            meeting_date=meeting.scheduled_start,
            agenda_topic=decision.agenda_topic,
            decision_text=decision.decision_text,
            context_notes=decision.context_notes,
        )
        for decision, meeting in rows
    ]
