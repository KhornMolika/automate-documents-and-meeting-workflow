import logging
import time
from typing import Dict

from deep_translator import MyMemoryTranslator

logger = logging.getLogger(__name__)


class KhmerTranslator:
    """Khmer-to-English translation with an in-process cache."""

    def __init__(self):
        self._cache: Dict[str, str] = {}

    def translate(self, text: str) -> Dict[str, float | str]:
        if not text.strip():
            return {"text": "", "latency_ms": 0.0}
        if text in self._cache:
            return {"text": self._cache[text], "latency_ms": 0.0}

        started = time.perf_counter()
        try:
            result = MyMemoryTranslator(source="km-KH", target="en-GB").translate(text)
            translated = (result or "").strip()
        except Exception as exc:
            logger.warning("Khmer translation failed: %s", exc)
            translated = ""

        if translated:
            self._cache[text] = translated
        return {
            "text": translated,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
