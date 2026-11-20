"""Deterministic transcript parsers.

The importer accepts plain text, WebVTT, SRT and DOCX transcripts. Nothing in
this module calls an AI model: the same file always produces the same segments.
"""

from __future__ import annotations

import html
import io
import re
from typing import Any, Dict, List

import docx

_CLOCK = r"\d{1,2}:\d{2}(?::\d{2})?"
_HEADER_RE = re.compile(rf"^(?P<speaker>.{{1,120}}?)\s+(?P<ts>{_CLOCK})$")
_HEADER_REVERSED_RE = re.compile(rf"^(?P<ts>{_CLOCK})\s+(?P<speaker>.{{1,120}})$")
_SPEAKER_LINE_RE = re.compile(r"^(?P<speaker>[^:]{1,120}):\s*(?P<text>.+)$")
_TIMESTAMPED_SPEAKER_RE = re.compile(
    rf"^\[?(?P<ts>{_CLOCK})\]?\s+(?P<speaker>[^:]{{1,120}}):\s*(?P<text>.+)$"
)
_VOICE_TAG_RE = re.compile(r"^<v\s+([^>]+)>(.*)$", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_METADATA_LABELS = {
    "meeting title",
    "date",
    "time",
    "duration",
    "attendees",
    "participants",
    "transcript",
    "recording",
}
_METADATA_LINES = {"transcript", "recording", "meeting transcript"}


def _seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except (TypeError, ValueError):
        return 0.0


def _clean(text: str) -> str:
    text = _VOICE_TAG_RE.sub(lambda match: match.group(2), text.strip())
    text = _HTML_TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _segment(
    speaker: str | None,
    text: str,
    start: float = 0.0,
    end: float = 0.0,
) -> Dict[str, Any]:
    clean_text = _clean(text)
    return {
        "speaker_label": (speaker or "Speaker").strip() or "Speaker",
        "start_timestamp": round(max(0.0, start), 3),
        "end_timestamp": round(max(start, end), 3),
        "original_text": clean_text,
        "translated_text": None,
        "confidence_score": 1.0,
        "language_detected": "imported",
    }


def _parse_timed_cues(content: str) -> List[Dict[str, Any]]:
    """Parse SRT or WebVTT cue blocks with timestamps."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized)
    segments: List[Dict[str, Any]] = []

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].upper().startswith("WEBVTT") or lines[0].upper().startswith("NOTE"):
            continue

        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue

        start_raw, _, end_raw = lines[timing_index].partition("-->")
        start = _seconds(start_raw.strip().split(" ")[0])
        end = _seconds(end_raw.strip().split(" ")[0])

        text_lines = lines[timing_index + 1 :]
        if not text_lines:
            continue

        speaker = None
        first = text_lines[0]
        voice = _VOICE_TAG_RE.match(first)
        if voice:
            speaker = voice.group(1).strip()
            text_lines[0] = voice.group(2)

        joined = " ".join(text_lines)
        speaker_match = _SPEAKER_LINE_RE.match(joined)
        if speaker_match and not voice:
            speaker = speaker_match.group("speaker").strip()
            joined = speaker_match.group("text")

        text = _clean(joined)
        if text:
            segments.append(_segment(speaker, text, start, end))

    return segments


def _estimate_end(text: str, start: float) -> float:
    words = len(text.split())
    return start + max(2.0, min(30.0, words * 0.45))


def _parse_plain_text(content: str) -> List[Dict[str, Any]]:
    """Parse TXT, pasted notes and DOCX paragraph text.

    Supports the common transcript shapes:
    - ``Speaker Name 00:01:23`` followed by the spoken text (Google Meet DOCX)
    - ``[00:01:23] Speaker Name: text``
    - ``Speaker Name: text``
    - plain paragraphs with no speaker labels
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    segments: List[Dict[str, Any]] = []
    current_speaker: str | None = None
    current_start = 0.0
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer
        text = " ".join(part.strip() for part in buffer if part.strip()).strip()
        buffer = []
        if not text:
            return
        segments.append(
            _segment(current_speaker, text, current_start, _estimate_end(text, current_start))
        )

    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.lower() in _METADATA_LINES:
            continue

        header = _HEADER_RE.match(line) or _HEADER_REVERSED_RE.match(line)
        if header:
            flush()
            current_speaker = header.group("speaker").strip()
            current_start = _seconds(header.group("ts"))
            continue

        timestamped = _TIMESTAMPED_SPEAKER_RE.match(line)
        if timestamped:
            flush()
            current_speaker = timestamped.group("speaker").strip()
            current_start = _seconds(timestamped.group("ts"))
            buffer.append(timestamped.group("text"))
            continue

        speaker_line = _SPEAKER_LINE_RE.match(line)
        if speaker_line and len(speaker_line.group("text")) > 1:
            speaker = speaker_line.group("speaker").strip()
            if speaker.lower() in _METADATA_LABELS:
                continue
            flush()
            current_speaker = speaker
            buffer.append(speaker_line.group("text"))
            continue

        buffer.append(line)

    flush()

    if not segments:
        text = _clean(normalized)
        if text:
            segments.append(_segment(None, text, 0.0, _estimate_end(text, 0.0)))
    return segments


def parse_transcript(filename: str, content: bytes) -> List[Dict[str, Any]]:
    """Parse an uploaded transcript into meeting transcript segments."""
    lower_name = (filename or "").lower()
    if lower_name.endswith(".docx"):
        try:
            document = docx.Document(io.BytesIO(content))
        except Exception as exc:
            raise ValueError("The DOCX transcript could not be read.") from exc
        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
            and not paragraph.style.name.lower().startswith(("heading", "title"))
        )
    else:
        text = content.decode("utf-8-sig", errors="replace")

    if not text.strip():
        raise ValueError("The transcript file is empty.")

    if lower_name.endswith((".vtt", ".srt")):
        segments = _parse_timed_cues(text)
        if segments:
            return segments
        # Fall back to plain text when the cue syntax is incomplete.
        return _parse_plain_text(text)

    return _parse_plain_text(text)
