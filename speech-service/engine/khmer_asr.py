import json
import logging
import time
from typing import Any, Dict

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

MODEL_REPO = "Vagabond404/khmer-asr-sota"
BLANK_ID = 72


class KhmerASR:
    """Khmer character-level CTC ASR using the 338 MB ONNX Khmer model."""

    def __init__(self):
        self._session = None
        self._vocab = None
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def _load(self):
        if self._loaded:
            return
        started = time.perf_counter()
        model_path = hf_hub_download(repo_id=MODEL_REPO, filename="khmer_asr_int8.onnx")
        vocab_path = hf_hub_download(repo_id=MODEL_REPO, filename="vocab.json")
        self._vocab = json.loads(open(vocab_path, encoding="utf-8").read())
        self._inverse_vocab = {index: token for token, index in self._vocab.items()}
        self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self._loaded = True
        logger.info("Khmer ASR model loaded in %.1fs", time.perf_counter() - started)

    def _decode(self, ids: np.ndarray) -> str:
        collapsed = []
        previous = None
        for raw in ids:
            token_id = int(raw)
            if token_id != previous:
                collapsed.append(token_id)
            previous = token_id

        pieces = []
        for token_id in collapsed:
            if token_id == BLANK_ID:
                continue
            token = self._inverse_vocab.get(token_id, "")
            if token in {"<s>", "</s>", "[PAD]", "[UNK]", "<pad>", "<unk>"}:
                continue
            pieces.append(" " if token == "|" else token)
        return "".join(pieces).strip()

    def transcribe(self, pcm_bytes: bytes) -> Dict[str, Any]:
        if not pcm_bytes:
            return {"text": "", "confidence": 0.0, "latency_ms": 0.0}

        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size < 1600:
            return {"text": "", "confidence": 0.0, "latency_ms": 0.0}

        peak = float(np.max(np.abs(audio)))
        if peak <= 0.002:
            return {"text": "", "confidence": 0.0, "latency_ms": 0.0}

        self._load()
        started = time.perf_counter()
        normalized = (audio - audio.mean()) / np.sqrt(audio.var() + 1e-7)
        logits = self._session.run(None, {"input_values": normalized[None, :]})[0]
        ids = logits.argmax(axis=-1)[0]
        text = self._decode(ids)

        if not any("\u1780" <= character <= "\u17ff" for character in text):
            text = ""

        probabilities = np.exp(logits[0] - logits[0].max(axis=-1, keepdims=True))
        probabilities /= probabilities.sum(axis=-1, keepdims=True)
        confidence = float(probabilities.max(axis=-1).mean()) if text else 0.0

        return {
            "text": text,
            "confidence": round(min(0.99, max(0.4, confidence)), 3),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
