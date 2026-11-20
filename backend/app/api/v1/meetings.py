import json
from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.meeting import (
    Meeting,
    MeetingAgenda,
    MeetingParticipant,
    MeetingTranscript,
    MeetingSummary,
    Decision,
    ActionItem,
)
from app.schemas.meeting import (
    MeetingCreate,
    MeetingOut,
    TranscriptSegmentCreate,
    TranscriptSegmentOut,
    TranscriptSegmentUpdate,
    MinutesOfMeetingSchema,
    MoMApprovalInput,
    MoMDraftInput,
    MeetingSummaryOut,
)
from app.services.llm_service import llm_service, AIServiceUnavailable

router = APIRouter(prefix="/meetings", tags=["Meeting Management"])


@router.post("", response_model=MeetingOut)
async def create_meeting(
    meeting_in: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    new_meeting = Meeting(
        title=meeting_in.title,
        description=meeting_in.description,
        scheduled_start=meeting_in.scheduled_start,
        scheduled_end=meeting_in.scheduled_end,
        department_id=meeting_in.department_id,
        created_by=current_user.id,
        status="Scheduled",
    )
    db.add(new_meeting)
    await db.flush()

    db.add(
        MeetingParticipant(
            meeting_id=new_meeting.id,
            user_id=current_user.id,
            role_in_meeting="Chairperson",
            attendance_status="Present",
        )
    )

    for item in meeting_in.agendas:
        agenda = MeetingAgenda(
            meeting_id=new_meeting.id,
            item_order=item.item_order,
            title=item.title,
            description=item.description,
            duration_minutes=item.duration_minutes,
        )
        db.add(agenda)

    await db.commit()

    # Re-fetch with agendas
    stmt = (
        select(Meeting)
        .where(Meeting.id == new_meeting.id)
        .options(
            selectinload(Meeting.agendas),
            selectinload(Meeting.participants),
            selectinload(Meeting.summary),
        )
    )
    res = await db.execute(stmt)
    return res.scalar_one()


@router.get("", response_model=List[MeetingOut])
async def list_meetings(
    department_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Meeting)
        .options(
            selectinload(Meeting.agendas),
            selectinload(Meeting.participants),
            selectinload(Meeting.summary).selectinload(MeetingSummary.decisions),
            selectinload(Meeting.summary).selectinload(MeetingSummary.action_items),
        )
        .order_by(desc(Meeting.scheduled_start))
        .offset(skip)
        .limit(limit)
    )
    if department_id:
        stmt = stmt.where(Meeting.department_id == department_id)
    if status_filter:
        stmt = stmt.where(Meeting.status == status_filter)

    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{meeting_id}/capture-info")
async def get_meeting_capture_info(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Minimal, public metadata so the capture extension can confirm the target meeting.

    Meeting IDs are unguessable UUIDs; only the title and status are exposed.
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"id": meeting.id, "title": meeting.title, "status": meeting.status}


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting_detail(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(
            selectinload(Meeting.agendas),
            selectinload(Meeting.participants),
            selectinload(Meeting.summary).selectinload(MeetingSummary.decisions),
            selectinload(Meeting.summary).selectinload(MeetingSummary.action_items),
        )
    )
    res = await db.execute(stmt)
    meeting = res.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting session not found")
    return meeting


@router.post("/{meeting_id}/start")
async def start_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting.status = "In Progress"
    await db.commit()
    return {"id": meeting.id, "status": meeting.status}


@router.post("/{meeting_id}/end")
async def end_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting.status = "Completed"
    await db.commit()
    return {"id": meeting.id, "status": meeting.status}


@router.post("/{meeting_id}/transcripts", response_model=TranscriptSegmentOut)
async def add_transcript_segment(
    meeting_id: str,
    segment_in: TranscriptSegmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    new_segment = MeetingTranscript(
        meeting_id=meeting_id,
        speaker_label=segment_in.speaker_label,
        start_timestamp=segment_in.start_timestamp,
        end_timestamp=segment_in.end_timestamp,
        original_text=segment_in.original_text,
        translated_text=segment_in.translated_text,
        confidence_score=segment_in.confidence_score,
        language_detected=segment_in.language_detected,
    )
    db.add(new_segment)
    await db.commit()
    await db.refresh(new_segment)
    return new_segment


@router.put("/{meeting_id}/transcripts/{transcript_id}", response_model=TranscriptSegmentOut)
async def update_transcript_segment(
    meeting_id: str,
    transcript_id: str,
    segment_in: TranscriptSegmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    segment = await db.get(MeetingTranscript, transcript_id)
    if not segment or segment.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="Transcript segment not found")
    if segment_in.original_text is not None:
        segment.original_text = segment_in.original_text.strip()
    if segment_in.translated_text is not None:
        segment.translated_text = segment_in.translated_text.strip() or None
    await db.commit()
    await db.refresh(segment)
    return segment


@router.get("/{meeting_id}/transcripts", response_model=List[TranscriptSegmentOut])
async def get_meeting_transcripts(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(MeetingTranscript)
        .where(
            MeetingTranscript.meeting_id == meeting_id,
            MeetingTranscript.original_text != "",
        )
        .order_by(MeetingTranscript.start_timestamp)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{meeting_id}/synthesize-mom", response_model=MinutesOfMeetingSchema)
async def synthesize_mom(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Triggers Gemini 1.5 Pro to synthesize raw transcripts into structured MoM draft.
    """
    stmt = (
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(selectinload(Meeting.agendas), selectinload(Meeting.participants), selectinload(Meeting.transcripts))
    )
    res = await db.execute(stmt)
    meeting = res.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.transcripts:
        raise HTTPException(status_code=400, detail="Add at least one transcript segment before generating MoM.")

    agendas = [a.title for a in meeting.agendas]
    transcripts_list = [
        {
            "speaker_label": t.speaker_label,
            "original_text": t.original_text,
            "translated_text": t.translated_text,
        }
        for t in meeting.transcripts
    ]

    try:
        mom_data = await llm_service.synthesize_meeting_mom(
            meeting_title=meeting.title,
            agendas=agendas,
            transcripts=transcripts_list,
        )
    except AIServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return mom_data


@router.put("/{meeting_id}/mom-draft", response_model=MeetingSummaryOut)
async def save_mom_draft(
    meeting_id: str,
    draft_in: MoMDraftInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    stmt = (
        select(MeetingSummary)
        .where(MeetingSummary.meeting_id == meeting_id)
        .options(selectinload(MeetingSummary.decisions), selectinload(MeetingSummary.action_items))
    )
    summary = (await db.execute(stmt)).scalar_one_or_none()

    if not summary:
        summary = MeetingSummary(
            meeting_id=meeting_id,
            executive_summary=draft_in.executive_summary,
            discussion_highlights=json.dumps(draft_in.discussion_points),
            is_verified=False,
        )
        db.add(summary)
        await db.flush()
    else:
        summary.executive_summary = draft_in.executive_summary
        summary.discussion_highlights = json.dumps(draft_in.discussion_points)
        summary.is_verified = False
        summary.verified_by = None
        summary.verified_at = None
        for decision in summary.decisions:
            await db.delete(decision)
        for item in summary.action_items:
            await db.delete(item)
        await db.flush()

    for index, decision in enumerate(draft_in.decisions, start=1):
        db.add(
            Decision(
                summary_id=summary.id,
                agenda_topic=decision.agenda_topic,
                decision_text=decision.decision_text,
                context_notes=decision.context_notes,
                order_index=index,
            )
        )

    for item in draft_in.action_items:
        db.add(
            ActionItem(
                summary_id=summary.id,
                task_description=item.task_description,
                raw_assignee_name=item.assignee_name,
                deadline=item.deadline,
                status="Pending",
            )
        )

    await db.commit()
    stmt = (
        select(MeetingSummary)
        .where(MeetingSummary.id == summary.id)
        .options(selectinload(MeetingSummary.decisions), selectinload(MeetingSummary.action_items))
    )
    return (await db.execute(stmt)).scalar_one()


@router.post("/{meeting_id}/approve-mom", response_model=MeetingSummaryOut)
async def approve_and_publish_mom(
    meeting_id: str,
    approval_in: MoMApprovalInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Human-in-the-Loop review confirmation: saves verified MoM and creates local DOCX/CSV exports.
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Check if a summary record already exists
    stmt = (
        select(MeetingSummary)
        .where(MeetingSummary.meeting_id == meeting_id)
        .options(selectinload(MeetingSummary.decisions), selectinload(MeetingSummary.action_items))
    )
    res = await db.execute(stmt)
    summary = res.scalar_one_or_none()

    if not summary:
        summary = MeetingSummary(
            meeting_id=meeting_id,
            executive_summary=approval_in.executive_summary,
            discussion_highlights=json.dumps(approval_in.discussion_points),
            is_verified=True,
            verified_by=current_user.id,
            verified_at=datetime.utcnow(),
        )
        db.add(summary)
        await db.flush()
    else:
        summary.executive_summary = approval_in.executive_summary
        summary.discussion_highlights = json.dumps(approval_in.discussion_points)
        summary.is_verified = True
        summary.verified_by = current_user.id
        summary.verified_at = datetime.utcnow()
        # Clean existing decisions & items to replace with verified version
        for d in summary.decisions:
            await db.delete(d)
        for a in summary.action_items:
            await db.delete(a)
        await db.flush()

    # Commit verified decisions
    for idx, d in enumerate(approval_in.decisions, start=1):
        dec_record = Decision(
            summary_id=summary.id,
            agenda_topic=d.agenda_topic,
            decision_text=d.decision_text,
            context_notes=d.context_notes,
            order_index=idx,
        )
        db.add(dec_record)

    # Commit verified action items
    for item in approval_in.action_items:
        act_record = ActionItem(
            summary_id=summary.id,
            task_description=item.task_description,
            raw_assignee_name=item.assignee_name,
            deadline=item.deadline,
            status="Pending",
        )
        db.add(act_record)

    meeting.status = "Completed"
    await db.commit()

    # Re-fetch summary with newly populated decisions and action items
    stmt = (
        select(MeetingSummary)
        .where(MeetingSummary.id == summary.id)
        .options(selectinload(MeetingSummary.decisions), selectinload(MeetingSummary.action_items))
    )
    res = await db.execute(stmt)
    refreshed_summary = res.scalar_one()
    return refreshed_summary
