from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


ACTION_ITEM_STATUSES = ("Pending", "In Progress", "Completed")


class ActionItemTrackerOut(BaseModel):
    id: str
    meeting_id: str
    meeting_title: str
    meeting_date: datetime
    task_description: str
    assignee_name: Optional[str] = None
    deadline: Optional[date] = None
    status: str
    is_overdue: bool
    created_at: datetime


class ActionItemStatusUpdate(BaseModel):
    status: str = Field(description="Pending, In Progress or Completed")


class DecisionTrackerOut(BaseModel):
    id: str
    meeting_id: str
    meeting_title: str
    meeting_date: datetime
    agenda_topic: Optional[str] = None
    decision_text: str
    context_notes: Optional[str] = None
