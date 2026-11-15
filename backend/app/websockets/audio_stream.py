import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets"])


class ConnectionManager:
    def __init__(self):
        # meeting_id -> list of subscriber WebSockets (e.g. Nuxt 3 dashboards)
        self.active_subscribers: Dict[str, Set[WebSocket]] = {}

    async def connect_subscriber(self, meeting_id: str, websocket: WebSocket):
        await websocket.accept()
        if meeting_id not in self.active_subscribers:
            self.active_subscribers[meeting_id] = set()
        self.active_subscribers[meeting_id].add(websocket)
        logger.info(f"Client subscribed to live transcripts for meeting {meeting_id}")

    def disconnect_subscriber(self, meeting_id: str, websocket: WebSocket):
        if meeting_id in self.active_subscribers:
            self.active_subscribers[meeting_id].discard(websocket)
            if not self.active_subscribers[meeting_id]:
                del self.active_subscribers[meeting_id]
        logger.info(f"Client disconnected from meeting {meeting_id}")

    async def broadcast_transcript(self, meeting_id: str, data: dict):
        if meeting_id in self.active_subscribers:
            dead_connections = set()
            for connection in self.active_subscribers[meeting_id]:
                try:
                    await connection.send_json(data)
                except Exception:
                    dead_connections.add(connection)
            for dead in dead_connections:
                self.active_subscribers[meeting_id].discard(dead)


manager = ConnectionManager()


@router.websocket("/ws/live-transcript/{meeting_id}")
async def websocket_live_transcript_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint for Nuxt 3 web clients to receive real-time bilingual transcripts.
    """
    await manager.connect_subscriber(meeting_id, websocket)
    try:
        while True:
            # Keep-alive ping/pong
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect_subscriber(meeting_id, websocket)


@router.websocket("/ws/audio/{meeting_id}")
async def websocket_audio_ingress_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint for the WXT Chrome Extension to stream 16kHz linear PCM audio chunks.
    """
    await websocket.accept()
    logger.info(f"Audio ingress stream started for meeting: {meeting_id}")

    chunk_counter = 0

    try:
        while True:
            # Receive binary linear PCM audio chunk from Chrome extension
            data = await websocket.receive_bytes()
            chunk_counter += 1

            # Real-time processing simulation/mock runner:
            # In production with local GPU, this routes to Omnilingual-ASR-Khm + Netra-NMT.
            # Here we provide a live simulation emitting verified bilingual sample turns:
            sample_turns = [
                ("សូមជម្រាបសួរលោកគ្រូអ្នកគ្រូទាំងអស់គ្នា ថ្ងៃនេះយើងប្រជុំ review the project proposal.",
                 "Good morning teachers and everyone, today we meet to review the project proposal."),
                ("សម្រាប់ curriculum ថ្មី យើងត្រូវ follow the latest MoEYS guidelines.",
                 "For the new curriculum, we need to follow the latest MoEYS guidelines."),
                ("Dean Lay Thou បាន approve budget allocation សម្រាប់ academic year 2026.",
                 "Dean Lay Thou has approved the budget allocation for academic year 2026."),
                ("សូមក្រុមការងារ finish the documentation មុនថ្ងៃ Friday ម៉ោង 5:00 PM.",
                 "Team please finish the documentation before Friday at 5:00 PM.")
            ]

            turn_idx = (chunk_counter - 1) % len(sample_turns)
            orig_sample, trans_sample = sample_turns[turn_idx]

            payload = {
                "type": "transcript_segment",
                "meeting_id": meeting_id,
                "speaker_label": f"Speaker {(chunk_counter % 2) + 1}",
                "start_timestamp": round((chunk_counter - 1) * 3.0, 1),
                "end_timestamp": round(chunk_counter * 3.0, 1),
                "original_text": orig_sample,
                "translated_text": trans_sample,
                "confidence_score": 0.96,
                "language_detected": "km-en",
            }

            # Broadcast immediately to all connected UI clients
            await manager.broadcast_transcript(meeting_id, payload)

            # Echo ack to extension
            await websocket.send_json({"status": "received", "chunk": chunk_counter})

    except WebSocketDisconnect:
        logger.info(f"Audio stream closed for meeting: {meeting_id}")
