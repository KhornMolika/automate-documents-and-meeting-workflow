"""Timestamped speech segmentation over 16 kHz mono PCM."""

from __future__ import annotations

from typing import List, Tuple

from engine.vad import WebRTCVoiceActivityDetector


def segment_pcm(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
    frame_duration_ms: int = 30,
    min_speech_ms: int = 300,
    max_segment_seconds: float = 30.0,
    padding_ms: int = 200,
) -> List[Tuple[float, float, bytes]]:
    """Return ``(start_seconds, end_seconds, pcm_slice)`` speech segments."""
    if not pcm_bytes:
        return []

    frame_bytes = int(sample_rate * frame_duration_ms / 1000) * 2
    frame_count = len(pcm_bytes) // frame_bytes
    if frame_count == 0:
        return []

    vad = WebRTCVoiceActivityDetector(mode=1, sample_rate=sample_rate, frame_duration_ms=frame_duration_ms)
    voiced = [
        vad.is_speech(pcm_bytes[index * frame_bytes : (index + 1) * frame_bytes])
        for index in range(frame_count)
    ]

    # Collapse voiced frames into runs, merging short pauses.
    merge_gap_frames = max(1, int(300 / frame_duration_ms))
    min_frames = max(1, int(min_speech_ms / frame_duration_ms))
    runs: List[Tuple[int, int]] = []
    start: int | None = None
    last_voiced: int | None = None

    for index, is_speech in enumerate(voiced):
        if is_speech:
            if start is None:
                start = index
            elif last_voiced is not None and index - last_voiced > merge_gap_frames:
                runs.append((start, last_voiced + 1))
                start = index
            last_voiced = index
        elif start is not None and last_voiced is not None and index - last_voiced > merge_gap_frames:
            runs.append((start, last_voiced + 1))
            start = None
            last_voiced = None

    if start is not None and last_voiced is not None:
        runs.append((start, last_voiced + 1))

    padding_frames = max(0, int(padding_ms / frame_duration_ms))
    max_frames = max(1, int(max_segment_seconds * 1000 / frame_duration_ms))
    segments: List[Tuple[float, float, bytes]] = []

    for run_start, run_end in runs:
        if run_end - run_start < min_frames:
            continue
        padded_start = max(0, run_start - padding_frames)
        padded_end = min(frame_count, run_end + padding_frames)
        cursor = padded_start
        while cursor < padded_end:
            chunk_end = min(padded_end, cursor + max_frames)
            if chunk_end - cursor >= min_frames:
                start_seconds = cursor * frame_duration_ms / 1000
                end_seconds = chunk_end * frame_duration_ms / 1000
                segments.append(
                    (
                        start_seconds,
                        end_seconds,
                        pcm_bytes[cursor * frame_bytes : chunk_end * frame_bytes],
                    )
                )
            cursor = chunk_end

    return segments
