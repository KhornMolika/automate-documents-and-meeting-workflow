from fastapi import FastAPI, File, HTTPException, Query, UploadFile
import numpy as np
from pydantic import BaseModel
from engine.vad import WebRTCVoiceActivityDetector
from engine.asr_khmer import OmnilingualASRKhm
from engine.khmer_asr import KhmerASR
from engine.translation import KhmerTranslator

app = FastAPI(
    title="AUB Local Speech & Translation Engine",
    version="1.3.0",
    description="On-premise Khmer ASR, English ASR, and Khmer-to-English translation.",
)

vad = WebRTCVoiceActivityDetector(mode=1)
asr = OmnilingualASRKhm()
khmer_asr = KhmerASR()
translator = KhmerTranslator()

LANGUAGES = {"auto", "km", "en"}


def has_khmer(text: str) -> bool:
    return any("\u1780" <= character <= "\u17ff" for character in text)


def normalize_pcm(pcm_bytes: bytes) -> bytes:
    """Normalize quiet speech before VAD.

    WebRTC VAD is level-sensitive: a quiet laptop microphone can be classified
    as silence even when the person is speaking. Normalizing first keeps quiet
    speech intelligible; digital silence is still rejected.
    """
    usable = len(pcm_bytes) - (len(pcm_bytes) % 2)
    if usable <= 0:
        return b""
    audio = np.frombuffer(pcm_bytes[:usable], dtype=np.int16).astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 0.002:
        return b""
    audio = audio / peak * 0.9
    return np.clip(audio * 32767.0, -32768, 32767).astype(np.int16).tobytes()


class InferenceResponse(BaseModel):
    original_text: str
    translated_text: str
    language_detected: str
    confidence: float
    asr_latency_ms: float
    nmt_latency_ms: float
    total_latency_ms: float
    engine: str


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "Khmer ASR + English ASR + translation",
        "device": asr.device,
        "whisper_loaded": asr.models_loaded,
        "khmer_model_loaded": khmer_asr.loaded,
        "languages": sorted(LANGUAGES),
    }


@app.post("/inference/transcribe-and-translate", response_model=InferenceResponse)
async def process_audio(
    file: UploadFile = File(...),
    language: str = Query("auto", description="auto, km (Khmer) or en (English)"),
):
    raw_pcm = await file.read()
    requested = language.strip().lower()
    if requested not in LANGUAGES:
        requested = "auto"

    try:
        normalized_pcm = normalize_pcm(raw_pcm)
        if not normalized_pcm:
            return {
                "original_text": "",
                "translated_text": "",
                "language_detected": "unknown",
                "confidence": 0.0,
                "asr_latency_ms": 0.0,
                "nmt_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "engine": "vad",
            }
        filtered_pcm = vad.filter_silence(normalized_pcm)
        if not filtered_pcm:
            return {
                "original_text": "",
                "translated_text": "",
                "language_detected": "unknown",
                "confidence": 0.0,
                "asr_latency_ms": 0.0,
                "nmt_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "engine": "vad",
            }

        if requested == "km":
            khmer_result = khmer_asr.transcribe(filtered_pcm)
            original_text = khmer_result["text"]
            confidence = khmer_result["confidence"]
            asr_latency = khmer_result["latency_ms"]
            engine = "khmer-asr-sota"
            detected = "km"
            translation = translator.translate(original_text)
        elif requested == "en":
            base_result = asr.transcribe(filtered_pcm, language="en")
            original_text = base_result.get("text", "")
            confidence = base_result.get("confidence", 0.0)
            asr_latency = base_result.get("latency_ms", 0.0)
            engine = base_result.get("engine", "faster-whisper")
            detected = "en"
            translation = {"text": original_text, "latency_ms": 0.0}
        else:
            base_result = asr.transcribe(filtered_pcm)
            detected = base_result.get("language_detected", "unknown")

            original_text = base_result.get("text", "")
            confidence = base_result.get("confidence", 0.0)
            asr_latency = base_result.get("latency_ms", 0.0)
            engine = base_result.get("engine", "faster-whisper")

            if detected == "km":
                khmer_result = khmer_asr.transcribe(filtered_pcm)
                if khmer_result["text"]:
                    original_text = khmer_result["text"]
                    confidence = khmer_result["confidence"]
                    asr_latency = khmer_result["latency_ms"]
                    engine = "khmer-asr-sota"
            elif detected != "en":
                # Whisper often mistakes Khmer for Thai or another nearby
                # language on short chunks. Prefer Khmer whenever the Khmer
                # model produces Khmer script.
                khmer_result = khmer_asr.transcribe(filtered_pcm)
                if khmer_result["text"] and has_khmer(khmer_result["text"]):
                    original_text = khmer_result["text"]
                    confidence = khmer_result["confidence"]
                    asr_latency = khmer_result["latency_ms"]
                    engine = "khmer-asr-sota"
                    detected = "km"

            if detected == "km":
                translation = translator.translate(original_text)
            else:
                translation = {"text": original_text, "latency_ms": 0.0}

    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    translated_text = str(translation.get("text", ""))
    total_latency = asr_latency + float(translation.get("latency_ms", 0.0))

    return {
        "original_text": original_text,
        "translated_text": translated_text,
        "language_detected": detected,
        "confidence": confidence,
        "asr_latency_ms": asr_latency,
        "nmt_latency_ms": translation.get("latency_ms", 0.0),
        "total_latency_ms": total_latency,
        "engine": engine,
    }
