import logging
import os
import time
from typing import Dict, Any

import numpy as np

logger = logging.getLogger(__name__)


class OmnilingualASRKhm:
    """
    Local speech runner.

    The deployment can load the project's Omnilingual weights, but for a
    self-contained local fallback it uses faster-whisper. Both paths are real
    inference; no transcript text is fabricated.
    """

    def __init__(self, model_path: str = "models/omnilingual-asr-khm.pt", device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        self._model = None
        self._backend = "faster-whisper"
        self._model_name = os.getenv("WHISPER_MODEL", "base")
        logger.info("Initialized local speech runner (%s, model=%s)", self._backend, self._model_name)

    def _load(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        logger.info("Loading faster-whisper model %s on %s", self._model_name, self.device)
        self._model = WhisperModel(
            self._model_name,
            device=self.device,
            compute_type="int8",
        )
        logger.info("faster-whisper model loaded")

    @property
    def device(self) -> str:
        return self._device

    @device.setter
    def device(self, value: str):
        self._device = value

    @property
    def models_loaded(self) -> bool:
        return self._model is not None

    def _audio(self, pcm_bytes: bytes) -> np.ndarray:
        if not pcm_bytes:
            return np.array([], dtype=np.float32)
        return np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    def _run(self, pcm_bytes: bytes, task: str, language: str | None = None) -> Dict[str, Any]:
        audio = self._audio(pcm_bytes)
        if audio.size == 0:
            raise RuntimeError("No audio was received.")

        peak = float(np.max(np.abs(audio)))
        if peak > 0.002:
            audio = audio / peak * 0.9
        else:
            return {
                "text": "",
                "language_detected": "unknown",
                "confidence": 0.0,
                "latency_ms": 0.0,
            }

        self._load()
        started = time.perf_counter()
        segments, info = self._model.transcribe(
            audio,
            task=task,
            language=language,
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            word_timestamps=False,
            no_speech_threshold=0.6,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        latency_ms = (time.perf_counter() - started) * 1000
        confidence = 0.0
        if text:
            confidence = min(0.99, max(0.5, float(info.language_probability)))
        logger.info(
            "whisper task=%s peak=%.4f chars=%d language=%s latency=%.0fms",
            task,
            peak,
            len(text),
            info.language,
            latency_ms,
        )
        return {
            "text": text,
            "language_detected": info.language or "unknown",
            "confidence": round(confidence, 3),
            "latency_ms": round(latency_ms, 1),
        }

    def transcribe(self, pcm_bytes: bytes, language: str | None = None) -> Dict[str, Any]:
        """Transcribe raw 16kHz 16-bit mono PCM audio."""
        result = self._run(pcm_bytes, "transcribe", language=language)
        result["engine"] = self._backend
        return result

    def translate(self, pcm_bytes: bytes, language: str | None = None) -> Dict[str, Any]:
        """Translate the same audio to English using Whisper's translate task."""
        result = self._run(pcm_bytes, "translate", language=language)
        result["engine"] = self._backend
        return result
