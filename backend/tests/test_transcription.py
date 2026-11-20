import functools
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from app.services import transcription


@pytest.mark.asyncio
async def test_rejects_private_network_urls():
    with pytest.raises(ValueError):
        await transcription.validate_source_url("http://127.0.0.1:8000/meeting.mp4")
    with pytest.raises(ValueError):
        await transcription.validate_source_url("http://localhost/meeting.mp4")


@pytest.mark.asyncio
async def test_rejects_non_http_urls():
    with pytest.raises(ValueError):
        await transcription.validate_source_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        await transcription.validate_source_url("ftp://example.com/meeting.mp4")


@pytest.mark.asyncio
async def test_rejects_live_meeting_pages():
    with pytest.raises(ValueError, match="live meeting link"):
        await transcription.validate_source_url("https://meet.google.com/abc-defg-hij")
    with pytest.raises(ValueError, match="live meeting link"):
        await transcription.validate_source_url("https://us02web.zoom.us/rec/share/abc")


@pytest.mark.asyncio
async def test_downloads_a_direct_transcript_link(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    transcript = source_dir / "meeting.vtt"
    transcript.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:04.000\n<v Speaker>Hello from the linked transcript.\n",
        encoding="utf-8",
    )
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(source_dir))
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = f"http://127.0.0.1:{server.server_port}/meeting.vtt"
        monkeypatch.setattr(transcription, "RECORDING_DIR", tmp_path / "downloads")
        monkeypatch.setattr(
            transcription,
            "validate_source_url",
            lambda value: _resolved(value),
        )
        path, kind, filename = await transcription.download_source(url)
        assert kind == "transcript"
        assert filename == "meeting.vtt"
        assert path.read_text(encoding="utf-8").startswith("WEBVTT")
    finally:
        server.shutdown()
        thread.join(timeout=5)


async def _resolved(value: str) -> str:
    return value
