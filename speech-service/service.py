import base64
import io
import logging
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from engine.asr_khmer import OmnilingualASRKhm
from engine.khmer_asr import KhmerASR
from engine.segmenter import segment_pcm
from engine.translation import KhmerTranslator

load_dotenv(Path(__file__).with_name(".env"))

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AUB Local Speech & Translation Engine",
    version="2.0.0",
    description="On-premise batch Khmer ASR, English ASR, and Khmer-to-English translation.",
)

asr = OmnilingualASRKhm()
khmer_asr = KhmerASR()
translator = KhmerTranslator()

LANGUAGES = {"auto", "km", "en"}
MAX_FILE_MB = int(os.getenv("MAX_SPEECH_FILE_MB", "500"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_TRANSCRIBE_MODEL = os.getenv("GEMINI_TRANSCRIBE_MODEL", "gemini-3.5-transcribe").strip()
GEMINI_TRANSCRIBE_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_TRANSCRIBE_FALLBACK_MODELS",
        "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3-flash-preview",
    ).split(",")
    if model.strip()
]
GEMINI_TRANSCRIBE_CHUNK_SECONDS = int(os.getenv("GEMINI_TRANSCRIBE_CHUNK_SECONDS", "120"))
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))


def has_khmer(text: str) -> bool:
    return any("\u1780" <= character <= "\u17ff" for character in text)


def normalize_khmer_text(text: str) -> str:
    """Tidy Khmer output without changing the recognized words."""
    text = re.sub(r"[ \t]+", " ", (text or "").strip())
    # Khmer words are written without spaces. Keep spaces around Latin words
    # and numbers, but remove them between Khmer characters.
    text = re.sub(r"(?<=[\u1780-\u17FF])\s+(?=[\u1780-\u17FF])", "", text)
    text = re.sub(r"\s*។\s*", "។", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def pcm_to_wav(pcm_bytes: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm_bytes)
    return buffer.getvalue()


def transcribe_with_gemini(
    pcm_bytes: bytes, translate: bool, model: str | None = None
) -> Dict[str, Any]:
    """Transcribe Khmer audio with Google's Gemini transcription model.

    The local Khmer CTC model is fast but can produce garbled words. Gemini's
    transcription model is materially better on Khmer script. If the key is
    absent, the caller falls back to the local model.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    model = model or GEMINI_TRANSCRIBE_MODEL
    prompt = (
        "Transcribe the audio verbatim in Khmer. Return only the transcript. "
        "Write natural Khmer: do not put spaces between Khmer words, use the Khmer "
        "sentence-ending mark ។ at sentence boundaries, and keep English words as spoken. "
        "Do not translate, summarize, number the lines, or add commentary."
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": base64.b64encode(pcm_to_wav(pcm_bytes)).decode(),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )

    last_error = f"Google transcription ({model}) returned no text."
    for _ in range(2):
        try:
            response = requests.post(
                url,
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            last_error = f"Google transcription ({model}) request failed: {exc}"
            continue

        if response.status_code != 200:
            try:
                message = response.json().get("error", {}).get("message", response.text[:300])
            except Exception:
                message = response.text[:300]
            last_error = f"Google transcription ({model}) error {response.status_code}: {message}"
            continue

        body = response.json()
        text_parts = []
        for candidate in body.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("text"):
                    text_parts.append(part["text"])
        text = " ".join(text_parts).strip().strip('"').strip()
        text = normalize_khmer_text(text)
        if not text:
            last_error = f"Google transcription ({model}) returned no text."
            continue
        if not has_khmer(text):
            last_error = f"Google transcription ({model}) did not return Khmer text."
            continue

        translated_text = None
        if translate:
            try:
                translation = translator.translate(text)
                translated_text = str(translation.get("text") or "").strip() or None
            except Exception as exc:
                logger.warning("Khmer translation failed: %s", exc)

        return {
            "text": text,
            "translated_text": translated_text,
            "language_detected": "km",
            "confidence": 0.0,
            "engine": f"google-{model}",
        }

    raise RuntimeError(last_error)


def normalize_pcm(pcm_bytes: bytes) -> bytes:
    """Normalize quiet speech before VAD and ASR."""
    usable = len(pcm_bytes) - (len(pcm_bytes) % 2)
    if usable <= 0:
        return b""
    audio = np.frombuffer(pcm_bytes[:usable], dtype=np.int16).astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 0.002:
        return b""
    audio = audio / peak * 0.9
    return np.clip(audio * 32767.0, -32768, 32767).astype(np.int16).tobytes()


class TranscriptSegment(BaseModel):
    speaker_label: str = "Speaker"
    start_timestamp: float
    end_timestamp: float
    original_text: str
    translated_text: str | None = None
    language_detected: str = "unknown"
    confidence_score: float = 0.0


class BatchTranscriptResponse(BaseModel):
    segments: List[TranscriptSegment]
    duration_seconds: float
    engine: str
    language: str


def transcribe_khmer_with_gemini(
    pcm_bytes: bytes, translate: bool
) -> tuple[List[TranscriptSegment], str]:
    """Transcribe Khmer in bounded chunks, one Gemini request per chunk.

    Sending the whole recording is both more accurate and much friendlier to the
    free API quota than one request per VAD segment. If the primary transcription
    model is unavailable, the configured Flash-Lite fallback is used.
    """
    bytes_per_second = 32000
    chunk_size = max(1, GEMINI_TRANSCRIBE_CHUNK_SECONDS) * bytes_per_second
    models = list(
        dict.fromkeys(
            model
            for model in [GEMINI_TRANSCRIBE_MODEL, *GEMINI_TRANSCRIBE_FALLBACK_MODELS]
            if model
        )
    )
    disabled_models: set[str] = set()
    segments: List[TranscriptSegment] = []
    engines: set[str] = set()

    for offset in range(0, len(pcm_bytes), chunk_size):
        chunk = pcm_bytes[offset : offset + chunk_size]
        if not chunk:
            continue
        start = offset / bytes_per_second
        end = start + len(chunk) / bytes_per_second
        result: Dict[str, Any] | None = None
        last_error = "Google transcription returned no Khmer text."

        for model in models:
            if model in disabled_models:
                continue
            try:
                result = transcribe_with_gemini(chunk, translate, model)
                break
            except Exception as exc:
                disabled_models.add(model)
                last_error = str(exc)
                logger.warning("Gemini model %s failed; trying the next model: %s", model, exc)

        if result is None:
            raise RuntimeError(last_error)

        text = str(result.get("text") or "").strip()
        if not text:
            continue
        engines.add(str(result.get("engine") or "google-gemini"))
        segments.append(
            TranscriptSegment(
                speaker_label="Speaker",
                start_timestamp=round(start, 2),
                end_timestamp=round(end, 2),
                original_text=text,
                translated_text=result.get("translated_text"),
                language_detected="km",
                confidence_score=float(result.get("confidence") or 0.0),
            )
        )

    if not segments:
        raise RuntimeError("Google transcription returned no Khmer text.")
    return segments, ", ".join(sorted(engines))


def transcribe_pcm(pcm_bytes: bytes, requested: str, translate: bool) -> Dict[str, Any]:
    normalized = normalize_pcm(pcm_bytes)
    if not normalized:
        return {"text": "", "translated_text": None, "language_detected": "unknown", "confidence": 0.0}

    try:
        if requested == "km":
            result = khmer_asr.transcribe(normalized)
            text = result["text"]
            confidence = result["confidence"]
            detected = "km"
            engine = "khmer-asr-sota"
        elif requested == "en":
            result = asr.transcribe(normalized, language="en")
            text = result.get("text", "")
            confidence = result.get("confidence", 0.0)
            detected = "en"
            engine = result.get("engine", "faster-whisper")
        else:
            result = asr.transcribe(normalized)
            detected = result.get("language_detected", "unknown")
            text = result.get("text", "")
            confidence = result.get("confidence", 0.0)
            engine = result.get("engine", "faster-whisper")

            if detected == "km":
                khmer_result = khmer_asr.transcribe(normalized)
                if khmer_result["text"]:
                    text = khmer_result["text"]
                    confidence = khmer_result["confidence"]
                    engine = "khmer-asr-sota"
            elif detected != "en":
                # Whisper can mistake Khmer for a nearby language on short clips.
                khmer_result = khmer_asr.transcribe(normalized)
                if khmer_result["text"] and has_khmer(khmer_result["text"]):
                    text = khmer_result["text"]
                    confidence = khmer_result["confidence"]
                    engine = "khmer-asr-sota"
                    detected = "km"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ASR failed: {exc}") from exc

    translated_text = None
    if translate and text and detected == "km":
        translation = translator.translate(text)
        translated_text = str(translation.get("text") or "").strip() or None

    return {
        "text": text.strip(),
        "translated_text": translated_text,
        "language_detected": detected,
        "confidence": confidence,
        "engine": engine,
    }


def decode_audio(path: Path, output_path: Path) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="ffmpeg is not installed. Install it to transcribe MP3/M4A/MP4 recordings.",
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode("utf-8", errors="ignore")[:500]
        raise HTTPException(status_code=400, detail=f"Could not decode the recording: {message}") from exc


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "Khmer ASR + English ASR + translation (batch)",
        "device": asr.device,
        "whisper_loaded": asr.models_loaded,
        "khmer_model_loaded": khmer_asr.loaded,
        "gemini_transcription_configured": bool(GEMINI_API_KEY),
        "gemini_transcription_model": GEMINI_TRANSCRIBE_MODEL if GEMINI_API_KEY else None,
        "gemini_transcription_fallbacks": (
            GEMINI_TRANSCRIBE_FALLBACK_MODELS if GEMINI_API_KEY else []
        ),
        "languages": sorted(LANGUAGES),
    }


@app.post("/transcribe-file", response_model=BatchTranscriptResponse)
async def transcribe_file(
    file: UploadFile = File(...),
    language: str = Query("auto", description="auto, km (Khmer) or en (English)"),
    translate: bool = Query(True, description="Translate Khmer segments to English"),
):
    requested = (language or "auto").strip().lower()
    if requested not in LANGUAGES:
        requested = "auto"

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded recording is empty.")
    if len(payload) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Recording exceeds {MAX_FILE_MB} MB.")

    suffix = Path(file.filename or "recording").suffix or ".bin"
    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / f"input{suffix}"
        pcm_path = Path(tmp) / "audio.pcm"
        input_path.write_bytes(payload)
        decode_audio(input_path, pcm_path)
        pcm = normalize_pcm(pcm_path.read_bytes())

    if not pcm:
        raise HTTPException(status_code=400, detail="No audible speech was found in the recording.")

    duration_seconds = round(len(pcm) / 2 / 16000, 2)

    if requested == "km" and GEMINI_API_KEY:
        try:
            segments, engine = transcribe_khmer_with_gemini(pcm, translate)
            return BatchTranscriptResponse(
                segments=segments,
                duration_seconds=duration_seconds,
                engine=engine,
                language=requested,
            )
        except Exception as exc:
            logger.warning(
                "Gemini Khmer transcription failed; falling back to the local model: %s",
                exc,
            )

    segments = segment_pcm(pcm)
    if not segments:
        raise HTTPException(status_code=400, detail="No speech segments were detected.")

    results: List[TranscriptSegment] = []
    engines: set[str] = set()
    for start, end, chunk in segments:
        result = transcribe_pcm(chunk, requested, translate)
        if not result["text"]:
            continue
        engines.add(str(result.get("engine", "")))
        results.append(
            TranscriptSegment(
                speaker_label="Speaker",
                start_timestamp=round(start, 2),
                end_timestamp=round(end, 2),
                original_text=result["text"],
                translated_text=result.get("translated_text"),
                language_detected=str(result.get("language_detected") or "unknown"),
                confidence_score=float(result.get("confidence") or 0.0),
            )
        )

    if not results:
        raise HTTPException(
            status_code=400,
            detail="Speech was detected but no text could be recognized. Check the language setting.",
        )

    return BatchTranscriptResponse(
        segments=results,
        duration_seconds=duration_seconds,
        engine=", ".join(sorted(engine for engine in engines if engine)),
        language=requested,
    )
