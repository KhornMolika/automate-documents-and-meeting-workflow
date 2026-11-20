"""Recording ingestion and batch transcription jobs.

The browser never talks to the speech service directly. A recording is saved
locally, a job row is created, and a background task calls the on-premise
Khmer ASR service. Transcript files are parsed deterministically instead.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote, urlparse

import httpx
from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.meeting import Meeting, MeetingTranscript, TranscriptionJob
from app.services.transcript_parser import parse_transcript

RECORDING_DIR = Path("./uploads/recordings")
MAX_REDIRECTS = 3
_CHUNK_SIZE = 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

_TRANSCRIPT_MIME_TYPES = {
    "text/plain",
    "text/vtt",
    "application/x-subrip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_RECORDING_MIME_PREFIXES = ("audio/", "video/")
_LIVE_MEETING_HOSTS = (
    "meet.google.com",
    "zoom.us",
    "teams.microsoft.com",
    "teams.live.com",
)


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _safe_filename(filename: str) -> str:
    name = Path(unquote(filename or "recording")).name
    name = _SAFE_NAME.sub("_", name).strip("._") or "recording"
    return name[:120]


def _recording_extension(filename: str) -> str:
    return _extension(filename) if _extension(filename) in settings.ALLOWED_RECORDING_EXTENSIONS else ""


def _is_allowed_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _is_host(hostname: str, candidates: tuple[str, ...]) -> bool:
    host = hostname.lower().strip(".")
    return any(host == candidate or host.endswith(f".{candidate}") for candidate in candidates)


async def validate_source_url(url: str) -> str:
    """Reject non-HTTP URLs and hosts that resolve to private networks (SSRF)."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// links are supported.")
    if parsed.username or parsed.password:
        raise ValueError("Links with embedded credentials are not supported.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("The link does not contain a valid hostname.")
    if _is_host(hostname, _LIVE_MEETING_HOSTS):
        raise ValueError(
            "This is a live meeting link, not a recording file. "
            "The app cannot join a live meeting. Download the recording or transcript "
            "from Meet, Zoom or Teams, then upload the file."
        )

    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror as exc:
        raise ValueError("The link hostname could not be resolved.") from exc

    resolved = {item[4][0] for item in addresses}
    if not resolved or not all(_is_allowed_address(address) for address in resolved):
        raise ValueError("The link points to a private or reserved network address.")
    return parsed.geturl()


def _kind_from_name_and_type(filename: str, content_type: str) -> str:
    extension = _extension(filename)
    if extension in settings.ALLOWED_TRANSCRIPT_EXTENSIONS:
        return "transcript"
    if extension in settings.ALLOWED_RECORDING_EXTENSIONS:
        return "recording"

    mime = content_type.split(";")[0].strip().lower() if content_type else ""
    if mime in _TRANSCRIPT_MIME_TYPES:
        return "transcript"
    if mime.startswith(_RECORDING_MIME_PREFIXES):
        return "recording"
    if mime in {"application/octet-stream", ""}:
        return "recording"
    raise ValueError(
        "The link did not return an audio/video or transcript file. "
        "Download the file and upload it instead."
    )


async def save_recording_upload(upload: UploadFile) -> Tuple[Path, str, int]:
    filename = _safe_filename(upload.filename or "recording")
    extension = _recording_extension(filename)
    if not extension:
        allowed = ", ".join(settings.ALLOWED_RECORDING_EXTENSIONS)
        raise ValueError(f"Unsupported recording type. Allowed: {allowed}.")

    RECORDING_DIR.mkdir(parents=True, exist_ok=True)
    path = RECORDING_DIR / f"{uuid.uuid4().hex}_{filename}"
    limit = settings.MAX_RECORDING_SIZE_MB * 1024 * 1024
    size = 0

    with path.open("wb") as target:
        while chunk := await upload.read(_CHUNK_SIZE):
            size += len(chunk)
            if size > limit:
                target.close()
                path.unlink(missing_ok=True)
                raise ValueError(
                    f"The recording is larger than {settings.MAX_RECORDING_SIZE_MB} MB."
                )
            target.write(chunk)

    if size == 0:
        path.unlink(missing_ok=True)
        raise ValueError("The uploaded recording is empty.")
    return path, filename, size


async def download_source(url: str) -> Tuple[Path, str, str]:
    """Download a direct recording/transcript link with size and SSRF limits."""
    current = await validate_source_url(url)
    limit = settings.MAX_RECORDING_SIZE_MB * 1024 * 1024
    RECORDING_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=False, timeout=60.0) as client:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("The link redirected without a destination.")
                    current = await validate_source_url(str(response.url.join(location)))
                    continue
                if response.status_code != 200:
                    raise ValueError(f"The link returned HTTP {response.status_code}.")

                content_type = response.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower()
                if mime == "text/html":
                    if _is_host(urlparse(current).hostname or "", ("drive.google.com", "docs.google.com")):
                        raise ValueError(
                            "This is a Google Drive share page, not a direct file. "
                            "Open Drive, download the recording or transcript, then upload it."
                        )
                    raise ValueError(
                        "The link opened a web page rather than a media file. "
                        "Download the recording and upload it instead."
                    )

                filename = Path(unquote(urlparse(current).path)).name or "download"
                kind = _kind_from_name_and_type(filename, content_type)

                if not _has_supported_suffix(filename, kind):
                    filename = f"{filename}.{'vtt' if kind == 'transcript' else 'mp4'}"

                path = RECORDING_DIR / f"{uuid.uuid4().hex}_{_safe_filename(filename)}"
                size = 0
                with path.open("wb") as target:
                    async for chunk in response.aiter_bytes(_CHUNK_SIZE):
                        size += len(chunk)
                        if size > limit:
                            target.close()
                            path.unlink(missing_ok=True)
                            raise ValueError(
                                f"The linked file is larger than {settings.MAX_RECORDING_SIZE_MB} MB."
                            )
                        target.write(chunk)
                if size == 0:
                    path.unlink(missing_ok=True)
                    raise ValueError("The linked file is empty.")
                return path, kind, filename

    raise ValueError("The link redirected too many times.")


def _has_supported_suffix(filename: str, kind: str) -> bool:
    extension = _extension(filename)
    if kind == "transcript":
        return extension in settings.ALLOWED_TRANSCRIPT_EXTENSIONS
    return extension in settings.ALLOWED_RECORDING_EXTENSIONS


async def call_speech_service(path: Path, language: str) -> List[Dict[str, Any]]:
    url = f"{settings.SPEECH_SERVICE_URL.rstrip('/')}/transcribe-file"
    try:
        async with httpx.AsyncClient(timeout=settings.SPEECH_TIMEOUT_SECONDS) as client:
            with path.open("rb") as audio:
                response = await client.post(
                    url,
                    params={"language": language, "translate": "true"},
                    files={"file": (path.name, audio, "application/octet-stream")},
                )
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"The speech service is not reachable at {settings.SPEECH_SERVICE_URL}. "
            "Start it with `uvicorn service:app --port 8001` from speech-service/."
        ) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "The speech service timed out. Try a shorter recording or start the GPU service."
        ) from exc

    if response.status_code != 200:
        detail = response.text[:500]
        try:
            detail = response.json().get("detail") or detail
        except Exception:
            pass
        raise RuntimeError(f"Speech service error: {detail}")

    payload = response.json()
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise RuntimeError(
            "No speech was detected in the recording. Check the audio or try another file."
        )
    return segments


async def replace_transcripts(db: AsyncSession, meeting_id: str, segments: List[Dict[str, Any]]) -> int:
    await db.execute(delete(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id))
    written = 0
    for item in segments:
        text = str(item.get("original_text") or "").strip()
        if not text:
            continue
        db.add(
            MeetingTranscript(
                meeting_id=meeting_id,
                speaker_label=str(item.get("speaker_label") or "Speaker")[:100],
                start_timestamp=float(item.get("start_timestamp") or 0.0),
                end_timestamp=float(item.get("end_timestamp") or 0.0),
                original_text=text,
                translated_text=(str(item.get("translated_text") or "").strip() or None),
                confidence_score=float(item.get("confidence_score") or 0.0),
                language_detected=str(item.get("language_detected") or "unknown")[:20],
            )
        )
        written += 1
    return written


async def run_transcription_job(job_id: str) -> None:
    """Background task: transcribe a recording and replace the meeting transcript."""
    async with AsyncSessionLocal() as db:
        job = await db.get(TranscriptionJob, job_id)
        if not job or job.status not in {"queued", "processing"}:
            return
        job.status = "processing"
        job.error = None
        await db.commit()

        try:
            source_path: Path | None = None
            kind = "recording"
            if job.source_type == "url":
                source_path, kind, _ = await download_source(job.source_name or "")
            elif job.source_name:
                source_path = Path(job.source_name)
                if not source_path.exists():
                    raise RuntimeError("The uploaded recording is no longer on disk.")
                if _extension(source_path.name) in settings.ALLOWED_TRANSCRIPT_EXTENSIONS:
                    kind = "transcript"

            if source_path is None:
                raise RuntimeError("The transcription source is missing.")

            if kind == "transcript":
                segments = parse_transcript(source_path.name, source_path.read_bytes())
            else:
                segments = await call_speech_service(source_path, job.language)

            written = await replace_transcripts(db, job.meeting_id, segments)
            if written == 0:
                raise RuntimeError("No speech was detected in the recording.")
            job.segment_count = written
            job.status = "completed"
            job.error = None
            await db.commit()
        except Exception as exc:
            await db.rollback()
            job = await db.get(TranscriptionJob, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)[:1000]
                await db.commit()


async def latest_job(db: AsyncSession, meeting_id: str) -> TranscriptionJob | None:
    stmt = (
        select(TranscriptionJob)
        .where(TranscriptionJob.meeting_id == meeting_id)
        .order_by(TranscriptionJob.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
