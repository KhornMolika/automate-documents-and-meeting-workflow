from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from engine.vad import WebRTCVoiceActivityDetector
from engine.asr_khmer import OmnilingualASRKhm
from engine.nmt_netra import NetraNMT

app = FastAPI(
    title="AUB Local Speech & NMT Inference Engine",
    version="1.0.0",
    description="On-premise GPU inference node for Omnilingual-ASR-Khm and Netra-NMT."
)

vad = WebRTCVoiceActivityDetector(mode=2)
asr = OmnilingualASRKhm()
nmt = NetraNMT()


class InferenceResponse(BaseModel):
    original_text: str
    translated_text: str
    language_detected: str
    confidence: float
    asr_latency_ms: float
    nmt_latency_ms: float
    total_latency_ms: float


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "Omnilingual ASR + Netra-NMT",
        "device": asr.device,
        "cuda_available": False, # Dynamically detected in production
    }


@app.post("/inference/transcribe-and-translate", response_model=InferenceResponse)
async def process_audio(file: UploadFile = File(...)):
    raw_pcm = await file.read()

    # 1. VAD filter silence
    filtered_pcm = vad.filter_silence(raw_pcm)

    # 2. ASR Speech-to-Text
    asr_res = asr.transcribe(filtered_pcm)

    # 3. Neural Machine Translation
    nmt_res = nmt.translate(asr_res["text"])

    total_latency = asr_res["latency_ms"] + nmt_res["latency_ms"]

    return {
        "original_text": asr_res["text"],
        "translated_text": nmt_res["translated_text"],
        "language_detected": asr_res["language_detected"],
        "confidence": asr_res["confidence"],
        "asr_latency_ms": asr_res["latency_ms"],
        "nmt_latency_ms": nmt_res["latency_ms"],
        "total_latency_ms": total_latency,
    }
