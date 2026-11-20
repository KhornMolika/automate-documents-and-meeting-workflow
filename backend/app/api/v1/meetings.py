import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document
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
    MeetingPage,
    MeetingSummaryOut,
    MeetingUpdate,
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


def _can_manage_meeting(meeting: Meeting, current_user: User) -> bool:
    if current_user.is_superuser:
        return True
    if not current_user.department_id:
        return True
    return meeting.department_id == current_user.department_id


def _remove_export_files(meeting_id: str) -> None:
    export_dir = Path("./exports")
    for filename in (f"mom_{meeting_id}.docx", f"action_items_{meeting_id}.csv"):
        (export_dir / filename).unlink(missing_ok=True)


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


@router.get("", response_model=MeetingPage)
async def list_meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    view: Literal["all", "scheduled", "draft", "published"] = "all",
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    conditions = []
    if current_user.department_id:
        conditions.append(Meeting.department_id == current_user.department_id)
    if q and q.strip():
        conditions.append(Meeting.title.ilike(f"%{q.strip()}%"))

    def with_view(statement, selected_view: str):
        if selected_view == "scheduled":
            return statement.where(~Meeting.summary.has())
        if selected_view == "draft":
            return statement.where(Meeting.summary.has(MeetingSummary.is_verified.is_(False)))
        if selected_view == "published":
            return statement.where(Meeting.summary.has(MeetingSummary.is_verified.is_(True)))
        return statement

    counts: dict[str, int] = {}
    for key in ("all", "scheduled", "draft", "published"):
        count_stmt = with_view(
            select(func.count()).select_from(Meeting).where(*conditions),
            key,
        )
        counts[key] = int(await db.scalar(count_stmt) or 0)

    total = counts[view]
    pages = max(1, (total + page_size - 1) // page_size)
    if page > pages:
        page = pages

    stmt = with_view(
        select(Meeting)
        .where(*conditions)
        .options(*_meeting_options())
        .order_by(desc(Meeting.scheduled_start), desc(Meeting.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size),
        view,
    )
    items = (await db.execute(stmt)).scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "counts": counts,
    }


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


@router.patch("/{meeting_id}", response_model=MeetingOut)
async def update_meeting(
    meeting_id: str,
    meeting_in: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(Meeting).where(Meeting.id == meeting_id).options(*_meeting_options())
    meeting = (await db.execute(stmt)).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not _can_manage_meeting(meeting, current_user):
        raise HTTPException(status_code=403, detail="You cannot edit this meeting.")

    if meeting_in.title is not None:
        title = meeting_in.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Meeting title cannot be empty.")
        meeting.title = title
    if meeting_in.description is not None:
        meeting.description = meeting_in.description.strip() or None
    if meeting_in.scheduled_start is not None:
        meeting.scheduled_start = meeting_in.scheduled_start
    if meeting_in.scheduled_end is not None:
        meeting.scheduled_end = meeting_in.scheduled_end
    if meeting.scheduled_end <= meeting.scheduled_start:
        raise HTTPException(status_code=400, detail="The meeting end must be after its start.")

    await db.commit()
    stmt = select(Meeting).where(Meeting.id == meeting_id).options(*_meeting_options())
    return (await db.execute(stmt)).scalar_one()


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    stmt = (
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(
            *_meeting_options(),
            selectinload(Meeting.transcripts),
            selectinload(Meeting.transcription_jobs),
        )
    )
    meeting = (await db.execute(stmt)).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not _can_manage_meeting(meeting, current_user):
        raise HTTPException(status_code=403, detail="You cannot delete this meeting.")

    archived_stmt = (
        select(Document)
        .where(Document.drive_file_id == meeting_id)
        .options(selectinload(Document.versions))
    )
    for document in (await db.execute(archived_stmt)).scalars().all():
        await db.delete(document)

    for job in meeting.transcription_jobs:
        if job.source_type == "upload" and job.source_name:
            Path(job.source_name).unlink(missing_ok=True)

    await db.delete(meeting)
    await db.commit()
    _remove_export_files(meeting_id)
    return Response(status_code=204)


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
