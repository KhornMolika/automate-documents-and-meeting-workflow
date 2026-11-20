import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    calendar_event_id: Mapped[str] = mapped_column(String(255), nullable=True)
    meet_link: Mapped[str] = mapped_column(String(500), nullable=True)
    department_id: Mapped[str] = mapped_column(String(36), ForeignKey("departments.id"), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Scheduled") # Scheduled, In Progress, Completed, Cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    department = relationship("Department", back_populates="meetings")
    creator = relationship("User", back_populates="created_meetings")
    agendas = relationship("MeetingAgenda", back_populates="meeting", cascade="all, delete-orphan", order_by="MeetingAgenda.item_order")
    participants = relationship("MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")
    transcripts = relationship("MeetingTranscript", back_populates="meeting", cascade="all, delete-orphan", order_by="MeetingTranscript.start_timestamp")
    summary = relationship("MeetingSummary", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    transcription_jobs = relationship("TranscriptionJob", back_populates="meeting", cascade="all, delete-orphan")

    @property
    def participant_count(self) -> int:
        return len(self.participants)


class MeetingAgenda(Base):
    __tablename__ = "meeting_agendas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    item_order: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=15)

    meeting = relationship("Meeting", back_populates="agendas")


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    external_name: Mapped[str] = mapped_column(String(255), nullable=True)
    external_email: Mapped[str] = mapped_column(String(255), nullable=True)
    role_in_meeting: Mapped[str] = mapped_column(String(50), default="Attendee") # Chairperson, Secretary, Attendee
    attendance_status: Mapped[str] = mapped_column(String(50), default="Invited") # Invited, Present, Absent, Excused

    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User", back_populates="meeting_participations")


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    speaker_label: Mapped[str] = mapped_column(String(100), default="Speaker 1")
    start_timestamp: Mapped[float] = mapped_column(Float, default=0.0)
    end_timestamp: Mapped[float] = mapped_column(Float, default=0.0)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.95)
    language_detected: Mapped[str] = mapped_column(String(20), default="km-en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcripts")


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("meetings.id", ondelete="CASCADE"), unique=True, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    discussion_highlights: Mapped[str] = mapped_column(Text, nullable=True) # JSON list of strings
    mom_doc_id: Mapped[str] = mapped_column(String(255), nullable=True)
    mom_doc_link: Mapped[str] = mapped_column(String(500), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="summary")
    decisions = relationship("Decision", back_populates="summary", cascade="all, delete-orphan", order_by="Decision.order_index")
    action_items = relationship("ActionItem", back_populates="summary", cascade="all, delete-orphan")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    summary_id: Mapped[str] = mapped_column(String(36), ForeignKey("meeting_summaries.id", ondelete="CASCADE"), nullable=False)
    agenda_topic: Mapped[str] = mapped_column(String(255), nullable=True)
    decision_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_notes: Mapped[str] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1)

    summary = relationship("MeetingSummary", back_populates="decisions")


class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")  # queued, processing, completed, failed
    language: Mapped[str] = mapped_column(String(20), default="km")
    source_type: Mapped[str] = mapped_column(String(20), default="upload")  # upload, url
    source_name: Mapped[str] = mapped_column(String(500), nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    segment_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcription_jobs")


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    summary_id: Mapped[str] = mapped_column(String(36), ForeignKey("meeting_summaries.id", ondelete="CASCADE"), nullable=False)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    responsible_person_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    raw_assignee_name: Mapped[str] = mapped_column(String(255), nullable=True)
    deadline: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Pending") # Pending, In Progress, Completed, Overdue
    sheets_row_index: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    summary = relationship("MeetingSummary", back_populates="action_items")
    responsible_person = relationship("User", back_populates="assigned_action_items")
