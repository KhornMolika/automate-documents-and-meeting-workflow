from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict


# Agenda schemas
class AgendaItemBase(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int = 15
    item_order: int = 1


class AgendaItemOut(AgendaItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: str


# Transcript schemas
class TranscriptSegmentCreate(BaseModel):
    speaker_label: str = "Speaker 1"
    start_timestamp: float
    end_timestamp: float
    original_text: str
    translated_text: Optional[str] = None
    confidence_score: float = 0.95
    language_detected: str = "km-en"


class TranscriptSegmentOut(TranscriptSegmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class TranscriptSegmentUpdate(BaseModel):
    original_text: Optional[str] = None
    translated_text: Optional[str] = None


# AI Extraction Schemas (Structured Pydantic v2 Models for Gemini 1.5 Pro)
class ActionItemSchema(BaseModel):
    task_description: str = Field(description="Clear, actionable task description")
    assignee_name: Optional[str] = Field(None, description="Explicitly named responsible person")
    deadline: Optional[date] = Field(None, description="Explicit deadline if mentioned, formatted as YYYY-MM-DD")
    confidence_score: float = Field(default=0.95, description="Extraction confidence between 0.0 and 1.0")


class DecisionSchema(BaseModel):
    agenda_topic: Optional[str] = Field(None, description="Related agenda topic")
    decision_text: str = Field(description="Formal resolution or agreed outcome")
    context_notes: Optional[str] = Field(None, description="Additional context or voting margin")


class MinutesOfMeetingSchema(BaseModel):
    meeting_title: str
    executive_summary: str = Field(description="Comprehensive 200-word executive summary of discussion")
    discussion_points: List[str] = Field(description="Key bullet points summarizing topics")
    decisions: List[DecisionSchema] = Field(description="List of formal agreed decisions")
    action_items: List[ActionItemSchema] = Field(description="List of extracted action items")


# Meeting Out schemas
class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agenda_topic: Optional[str] = None
    decision_text: str
    context_notes: Optional[str] = None
    order_index: int


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_description: str
    responsible_person_id: Optional[str] = None
    raw_assignee_name: Optional[str] = None
    deadline: Optional[date] = None
    status: str
    sheets_row_index: Optional[int] = None
    created_at: datetime


class MeetingSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    executive_summary: str
    discussion_highlights: Optional[str] = None
    mom_doc_id: Optional[str] = None
    mom_doc_link: Optional[str] = None
    is_verified: bool
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    decisions: List[DecisionOut] = []
    action_items: List[ActionItemOut] = []


class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    department_id: str
    agendas: List[AgendaItemBase] = []


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    calendar_event_id: Optional[str] = None
    meet_link: Optional[str] = None
    department_id: str
    status: str
    created_at: datetime
    participant_count: int = 0
    agendas: List[AgendaItemOut] = []
    summary: Optional[MeetingSummaryOut] = None


class MoMApprovalInput(BaseModel):
    executive_summary: str
    discussion_points: List[str]
    decisions: List[DecisionSchema]
    action_items: List[ActionItemSchema]
    export_to_google_docs: bool = True
    export_to_google_sheets: bool = True
    notify_attendees_gmail: bool = False


class MoMDraftInput(BaseModel):
    executive_summary: str
    discussion_points: List[str]
    decisions: List[DecisionSchema]
    action_items: List[ActionItemSchema]
