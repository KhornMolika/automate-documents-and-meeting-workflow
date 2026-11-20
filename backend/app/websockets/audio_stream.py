import array
import logging
import sys
from typing import Dict, Set

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.meeting import MeetingTranscript

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets"])


class ConnectionManager:
    def __init__(self):
        self.active_subscribers: Dict[str, Set[WebSocket]] = {}
        self.capture_states: Dict[str, dict] = {}

    def set_capture_state(self, meeting_id: str, state: dict):
        self.capture_states[meeting_id] = state

    async def connect_subscriber(self, meeting_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_subscribers.setdefault(meeting_id, set()).add(websocket)
        logger.info("Client subscribed to live transcripts for meeting %s", meeting_id)
        state = self.capture_states.get(meeting_id)
        if state:
            try:
                await websocket.send_json({"type": "capture_status", **state})
            except Exception:
                pass

    def disconnect_subscriber(self, meeting_id: str, websocket: WebSocket):
        if meeting_id in self.active_subscribers:
            self.active_subscribers[meeting_id].discard(websocket)
            if not self.active_subscribers[meeting_id]:
                del self.active_subscribers[meeting_id]
        logger.info("Client disconnected from meeting %s", meeting_id)

    async def broadcast(self, meeting_id: str, data: dict):
        for connection in list(self.active_subscribers.get(meeting_id, set())):
            try:
                await connection.send_json(data)
            except Exception:
                self.active_subscribers[meeting_id].discard(connection)


manager = ConnectionManager()


def _pcm_peak(data: bytes) -> float:
    """Return the absolute peak of 16-bit little-endian PCM as a 0..1 ratio."""
    usable = len(data) - (len(data) % 2)
    if usable <= 0:
        return 0.0
    samples = array.array("h")
    samples.frombytes(data[:usable])
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0
    return round(max(abs(min(samples)), abs(max(samples))) / 32768.0, 4)


@router.websocket("/ws/live-transcript/{meeting_id}")
async def websocket_live_transcript_endpoint(websocket: WebSocket, meeting_id: str):
    await manager.connect_subscriber(meeting_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect_subscriber(meeting_id, websocket)


@router.websocket("/ws/audio/{meeting_id}")
async def websocket_audio_ingress_endpoint(websocket: WebSocket, meeting_id: str):
    await websocket.accept()
    logger.info("Audio ingress stream started for meeting %s", meeting_id)
    chunk_counter = 0
    language = (websocket.query_params.get("language") or "auto").strip().lower()
    if language not in {"auto", "km", "en"}:
        language = "auto"
    try:
        chunk_seconds = float(websocket.query_params.get("chunk_seconds") or 3.0)
    except ValueError:
        chunk_seconds = 3.0
    chunk_seconds = min(10.0, max(1.0, chunk_seconds))
    mic = websocket.query_params.get("mic")
    tab = websocket.query_params.get("tab")
    source = (websocket.query_params.get("source") or "mixed").strip().lower()
    speaker_label = {"mic": "You", "tab": "Participants"}.get(source, "Speaker")
    if mic == "0":
        logger.warning("Audio ingress for meeting %s has no microphone (mic=0)", meeting_id)
    manager.set_capture_state(
        meeting_id,
        {
            "status": "connected",
            "chunk": 0,
            "language": language,
            "mic": mic,
            "tab": tab,
            "source": source,
        },
    )
    await manager.broadcast(
        meeting_id,
        {
            "type": "capture_status",
            "status": "connected",
            "chunk": 0,
            "mic": mic,
            "tab": tab,
            "source": source,
        },
    )

    try:
        while True:
            data = await websocket.receive_bytes()
            chunk_counter += 1
            peak = _pcm_peak(data)
            manager.set_capture_state(
                meeting_id,
                {
                    "status": "receiving",
                    "chunk": chunk_counter,
                    "bytes": len(data),
                    "peak": peak,
                    "mic": mic,
                    "tab": tab,
                    "source": source,
                },
            )
            await manager.broadcast(
                meeting_id,
                {
                    "type": "capture_status",
                    "status": "receiving",
                    "chunk": chunk_counter,
                    "bytes": len(data),
                    "peak": peak,
                    "mic": mic,
                    "tab": tab,
                    "source": source,
                },
            )

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{settings.SPEECH_SERVICE_URL}/inference/transcribe-and-translate",
                        files={"file": ("chunk.pcm", data, "application/octet-stream")},
                        params={"language": language},
                    )
                response.raise_for_status()
                result = response.json()
            except Exception as exc:
                logger.warning("Speech inference failed for meeting %s: %s", meeting_id, exc)
                await manager.broadcast(
                    meeting_id,
                    {
                        "type": "transcription_error",
                        "meeting_id": meeting_id,
                        "message": "The local speech engine is unavailable. Check the speech service and model weights.",
                    },
                )
                await websocket.send_json(
                    {"status": "error", "chunk": chunk_counter, "message": "Speech engine unavailable"}
                )
                continue

            payload = {
                "type": "transcript_segment",
                "meeting_id": meeting_id,
                "speaker_label": speaker_label,
                "start_timestamp": round((chunk_counter - 1) * chunk_seconds, 1),
                "end_timestamp": round(chunk_counter * chunk_seconds, 1),
                "original_text": result.get("original_text", ""),
                "translated_text": result.get("translated_text"),
                "confidence_score": result.get("confidence", 0.0),
                "language_detected": result.get("language_detected", "unknown"),
            }

            if not payload["original_text"].strip():
                await manager.broadcast(
                    meeting_id,
                    {
                        "type": "transcription_status",
                        "status": "no_speech",
                        "meeting_id": meeting_id,
                        "source": source,
                    },
                )
                await websocket.send_json({"status": "no_speech", "chunk": chunk_counter})
                continue

            try:
                async with AsyncSessionLocal() as session:
                    session.add(
                        MeetingTranscript(
                            meeting_id=meeting_id,
                            speaker_label=payload["speaker_label"],
                            start_timestamp=payload["start_timestamp"],
                            end_timestamp=payload["end_timestamp"],
                            original_text=payload["original_text"],
                            translated_text=payload["translated_text"],
                            confidence_score=payload["confidence_score"],
                            language_detected=payload["language_detected"],
                        )
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("Could not persist transcript for meeting %s: %s", meeting_id, exc)

            await manager.broadcast(meeting_id, payload)
            await websocket.send_json({"status": "received", "chunk": chunk_counter})

    except WebSocketDisconnect:
        logger.info("Audio stream closed for meeting %s", meeting_id)
    finally:
        manager.set_capture_state(
            meeting_id,
            {
                "status": "disconnected",
                "chunk": chunk_counter,
                "mic": mic,
                "tab": tab,
                "source": source,
            },
        )
        await manager.broadcast(
            meeting_id,
            {
                "type": "capture_status",
                "status": "disconnected",
                "chunk": chunk_counter,
                "mic": mic,
                "tab": tab,
                "source": source,
            },
        )
