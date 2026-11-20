import io

import docx
import pytest

from app.services.transcript_parser import parse_transcript


def test_plain_text_speaker_lines():
    content = (
        "Dean Lay Thou: We need to review all proposals before Friday.\n"
        "Khorn Molika: I will submit the ethics approval.\n"
    ).encode()
    segments = parse_transcript("meeting.txt", content)
    assert len(segments) == 2
    assert segments[0]["speaker_label"] == "Dean Lay Thou"
    assert segments[0]["original_text"].startswith("We need to review")
    assert segments[1]["speaker_label"] == "Khorn Molika"


def test_google_meet_style_headers():
    content = (
        "Dean Lay Thou 00:00:12\n"
        "We need to review the proposals.\n\n"
        "Khorn Molika 00:00:30\n"
        "I will submit the approval.\n"
    ).encode()
    segments = parse_transcript("meeting.txt", content)
    assert len(segments) == 2
    assert segments[0]["speaker_label"] == "Dean Lay Thou"
    assert segments[0]["start_timestamp"] == 12
    assert segments[1]["start_timestamp"] == 30


def test_webvtt_voice_tags_and_timestamps():
    content = b"""WEBVTT

00:00:01.000 --> 00:00:04.500
<v Dean Lay Thou>Please review the proposal.

00:00:05.000 --> 00:00:08.000
<v Khorn Molika>I will send the report.
"""
    segments = parse_transcript("meeting.vtt", content)
    assert len(segments) == 2
    assert segments[0]["speaker_label"] == "Dean Lay Thou"
    assert segments[0]["start_timestamp"] == 1
    assert segments[0]["end_timestamp"] == 4.5
    assert segments[1]["start_timestamp"] == 5


def test_srt_timestamps_and_speaker_prefix():
    content = b"""1
00:00:03,000 --> 00:00:06,250
Dean Lay Thou: The budget is approved.

2
00:00:07,000 --> 00:00:09,000
Khorn Molika: I will update the plan.
"""
    segments = parse_transcript("meeting.srt", content)
    assert len(segments) == 2
    assert segments[0]["start_timestamp"] == 3
    assert segments[0]["end_timestamp"] == 6.25
    assert segments[0]["speaker_label"] == "Dean Lay Thou"


def test_docx_transcript():
    document = docx.Document()
    document.add_paragraph("Dean Lay Thou 00:00:10")
    document.add_paragraph("The committee approved the proposal.")
    buffer = io.BytesIO()
    document.save(buffer)

    segments = parse_transcript("meeting.docx", buffer.getvalue())
    assert len(segments) == 1
    assert segments[0]["speaker_label"] == "Dean Lay Thou"
    assert segments[0]["start_timestamp"] == 10
    assert "approved the proposal" in segments[0]["original_text"]


def test_empty_transcript_is_rejected():
    with pytest.raises(ValueError):
        parse_transcript("empty.txt", b"   \n")
