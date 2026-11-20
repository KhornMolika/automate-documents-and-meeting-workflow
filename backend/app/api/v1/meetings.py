import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.meeting import (
    ActionItem,
    Decision,
    Meeting,
    MeetingAgenda,
    MeetingParticipant,
    MeetingSummary,
    MeetingTranscript,
    TranscriptionJob,
)
from app.models.user import User
from app.schemas.meeting import (
    MeetingCreate,
    MeetingOut,
    MeetingSummaryOut,
    MinutesOfMeetingSchema,
    MoMApprovalInput,
    MoMDraftInput,
    RecordingUrlInput,
    TranscriptImportResult,
    TranscriptSegmentOut,
    TranscriptSegmentUpdate,
    TranscriptionJobOut,
)
from app.services.llm_service import AIServiceUnavailable, llm_service
from app.services.minutes import export_verified_minutes
from app.services.transcript_parser import parse_transcript
from app.services.transcription import (
    latest_job,
    replace_transcripts,
    run_transcription_job,
    save_recording_upload,
    validate_source_url,
)

router = APIRouter(prefix="/meetings", tags=["Meeting Management"])

ALLOWED_LANGUAGES = {"km", "en", "auto"}


def _meeting_options():
    return (
        selectinload(Meeting.agendas),
        selectinload(Meeting.participants).selectinload(MeetingParticipant.user),
        selectinload(Meeting.department),
        selectinload(Meeting.summary).selectinload(MeetingSummary.decisions),
        selectinload(Meeting.summary).selectinload(MeetingSummary.action_items),
    )


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
        db.add(
            MeetingAgenda(
                meeting_id=new_meeting.id,
                item_order=item.item_order,
                title=item.title,
                description=item.description,
                duration_minutes=item.duration_minutes,
            )
        )

    await db.commit()
    stmt = select(Meeting).where(Meeting.id == new_meeting.id).options(*_meeting_options())
    return (await db.execute(stmt)).scalar_one()


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
        .options(*_meeting_options())
        .order_by(desc(Meeting.scheduled_start))
        .offset(skip)
        .limit(limit)
    )
    if department_id:
        stmt = stmt.where(Meeting.department_id == department_id)
    if status_filter:
        stmt = stmt.where(Meeting.status == status_filter)

    return (await db.execute(stmt)).scalars().all()


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting_detail(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(Meeting).where(Meeting.id == meeting_id).options(*_meeting_options())
    meeting = (await db.execute(stmt)).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting session not found")
    return meeting


@router.post("/{meeting_id}/recording", response_model=TranscriptionJobOut)
async def upload_recording(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("km"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if language not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Language must be km, en or auto.")
    try:
        path, _filename, _size = await save_recording_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = TranscriptionJob(
        meeting_id=meeting_id,
        status="queued",
        language=language,
        source_type="upload",
        source_name=str(path),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    background_tasks.add_task(run_transcription_job, job.id)
    return job


@router.post("/{meeting_id}/from-link", response_model=TranscriptionJobOut)
async def transcribe_from_link(
    meeting_id: str,
    payload: RecordingUrlInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if payload.language not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Language must be km, en or auto.")
    try:
        url = await validate_source_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = TranscriptionJob(
        meeting_id=meeting_id,
        status="queued",
        language=payload.language,
        source_type="url",
        source_name=url,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    background_tasks.add_task(run_transcription_job, job.id)
    return job


@router.get("/{meeting_id}/transcription", response_model=Optional[TranscriptionJobOut])
async def get_transcription_job(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return await latest_job(db, meeting_id)


@router.post("/{meeting_id}/transcripts/import", response_model=TranscriptImportResult)
async def import_transcript(
    meeting_id: str,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not file and not (text and text.strip()):
        raise HTTPException(status_code=400, detail="Provide a transcript file or pasted text.")

    if file:
        filename = file.filename or "transcript.txt"
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in settings.ALLOWED_TRANSCRIPT_EXTENSIONS:
            allowed = ", ".join(settings.ALLOWED_TRANSCRIPT_EXTENSIONS)
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported transcript type. Allowed: {allowed}.",
            )
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="The transcript file is larger than 10 MB.")
    else:
        filename = "pasted-notes.txt"
        content = (text or "").encode("utf-8")

    try:
        segments = parse_transcript(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = await db.scalar(
        select(MeetingTranscript.id).where(MeetingTranscript.meeting_id == meeting_id).limit(1)
    )
    written = await replace_transcripts(db, meeting_id, segments)
    if written == 0:
        raise HTTPException(status_code=400, detail="The transcript did not contain readable text.")
    await db.commit()
    return {"imported": written, "replaced": 1 if existing else 0}


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
    if segment_in.speaker_label is not None:
        segment.speaker_label = segment_in.speaker_label.strip() or "Speaker"
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
        .order_by(MeetingTranscript.start_timestamp, MeetingTranscript.created_at)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/{meeting_id}/synthesize-mom", response_model=MinutesOfMeetingSchema)
async def synthesize_mom(
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
            selectinload(Meeting.transcripts),
        )
    )
    meeting = (await db.execute(stmt)).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.transcripts:
        raise HTTPException(
            status_code=400,
            detail="Add a transcript before generating minutes.",
        )

    agendas = [agenda.title for agenda in meeting.agendas]
    transcripts = [
        {
            "speaker_label": item.speaker_label,
            "original_text": item.original_text,
            "translated_text": item.translated_text,
        }
        for item in meeting.transcripts
    ]

    try:
        return await llm_service.synthesize_meeting_mom(
            meeting_title=meeting.title,
            agendas=agendas,
            transcripts=transcripts,
        )
    except AIServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one()


@router.post("/{meeting_id}/approve-mom", response_model=MeetingSummaryOut)
async def approve_and_publish_mom(
    meeting_id: str,
    approval_in: MoMApprovalInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Verify the minutes, write DOCX/CSV exports and archive them as a Document."""
    stmt = select(Meeting).where(Meeting.id == meeting_id).options(*_meeting_options())
    meeting = (await db.execute(stmt)).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    summary = meeting.summary
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
        for decision in summary.decisions:
            await db.delete(decision)
        for item in summary.action_items:
            await db.delete(item)
        await db.flush()

    for index, decision in enumerate(approval_in.decisions, start=1):
        db.add(
            Decision(
                summary_id=summary.id,
                agenda_topic=decision.agenda_topic,
                decision_text=decision.decision_text,
                context_notes=decision.context_notes,
                order_index=index,
            )
        )

    for item in approval_in.action_items:
        db.add(
            ActionItem(
                summary_id=summary.id,
                task_description=item.task_description,
                raw_assignee_name=item.assignee_name,
                deadline=item.deadline,
                status="Pending",
            )
        )

    meeting.status = "Completed"
    await db.flush()

    stmt = (
        select(MeetingSummary)
        .where(MeetingSummary.id == summary.id)
        .options(selectinload(MeetingSummary.decisions), selectinload(MeetingSummary.action_items))
        .execution_options(populate_existing=True)
    )
    verified = (await db.execute(stmt)).scalar_one()
    await export_verified_minutes(db, meeting, verified)
    await db.commit()

    stmt = (
        select(MeetingSummary)
        .where(MeetingSummary.id == summary.id)
        .options(selectinload(MeetingSummary.decisions), selectinload(MeetingSummary.action_items))
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one()
