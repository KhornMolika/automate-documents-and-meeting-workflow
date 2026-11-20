import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.schemas.meeting import MinutesOfMeetingSchema
from app.services.prompts import build_document_summary_prompt, build_mom_prompt

logger = logging.getLogger(__name__)


class AIServiceUnavailable(RuntimeError):
    """Raised when Gemini is not configured or cannot return a usable response."""


_RESPONSE_CACHE: dict[str, tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 600


def _parse_json_response(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                data = json.loads(repaired)
            except json.JSONDecodeError:
                continue
        if isinstance(data, dict):
            return data
    raise ValueError("Gemini did not return valid JSON.")


class GeminiService:
    def __init__(self):
        self.api_key = (settings.GEMINI_API_KEY or "").strip()
        self.model_name = settings.GEMINI_MODEL
        self.timeout = settings.GEMINI_TIMEOUT_SECONDS
        self.total_timeout = settings.GEMINI_TOTAL_TIMEOUT_SECONDS
        if self.api_key:
            logger.info("Gemini REST client configured with model %s", self.model_name)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _url(self, model: str) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )

    def _models(self) -> List[str]:
        models = [self.model_name, *settings.GEMINI_FALLBACK_MODELS]
        return list(dict.fromkeys(model for model in models if model))

    async def _generate_json(self, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise AIServiceUnavailable("GEMINI_API_KEY is not configured.")

        cache_key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        now = time.monotonic()
        cached = _RESPONSE_CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
        for key, (stored_at, _) in list(_RESPONSE_CACHE.items()):
            if now - stored_at >= _CACHE_TTL_SECONDS:
                _RESPONSE_CACHE.pop(key, None)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json",
            },
        }
        last_error = "Gemini did not return a usable response."
        started = time.monotonic()

        for model in self._models():
            for attempt in range(2):
                remaining = self.total_timeout - (time.monotonic() - started)
                if remaining <= 1:
                    raise AIServiceUnavailable(
                        f"Gemini took longer than {self.total_timeout}s. Try again in a moment."
                    )
                logger.info("Gemini request model=%s attempt=%d", model, attempt + 1)
                try:
                    async with httpx.AsyncClient(timeout=min(self.timeout, remaining)) as client:
                        response = await client.post(
                            self._url(model),
                            headers={
                                "x-goog-api-key": self.api_key,
                                "Content-Type": "application/json",
                            },
                            json=payload,
                        )
                except httpx.ConnectError:
                    last_error = "Gemini is not reachable. Check your internet connection."
                    await asyncio.sleep(1)
                    continue
                except httpx.TimeoutException:
                    last_error = "Gemini timed out. Try again in a moment."
                    await asyncio.sleep(1)
                    continue

                if response.status_code in {404, 429, 500, 502, 503, 504}:
                    try:
                        message = response.json().get("error", {}).get("message", "")
                    except Exception:
                        message = response.text[:300]
                    last_error = f"Gemini ({model}) returned HTTP {response.status_code}: {message}"
                    if attempt == 0:
                        await asyncio.sleep(1.5)
                    continue

                if response.status_code != 200:
                    message = response.text[:500]
                    try:
                        message = response.json().get("error", {}).get("message", message)
                    except Exception:
                        pass
                    raise AIServiceUnavailable(
                        f"Gemini returned HTTP {response.status_code}: {message}"
                    )

                try:
                    body = response.json()
                    text_parts = []
                    for candidate in body.get("candidates", []):
                        for part in candidate.get("content", {}).get("parts", []):
                            if part.get("text"):
                                text_parts.append(part["text"])
                    raw = "".join(text_parts)
                    data = _parse_json_response(raw)
                    _RESPONSE_CACHE[cache_key] = (time.monotonic(), data)
                    return data
                except Exception as exc:
                    last_error = f"Gemini ({model}) returned an invalid response: {exc}"
                    logger.error(last_error)
                    break

        raise AIServiceUnavailable(last_error)

    async def summarize_document(
        self,
        title: str,
        text: str,
        language: str = "en",
    ) -> Dict[str, Any]:
        if not text.strip():
            raise AIServiceUnavailable("No extracted text is available to summarize.")
        data = await self._generate_json(
            build_document_summary_prompt(title, text, language=language)
        )
        if not isinstance(data.get("abstract_summary"), str) or not data["abstract_summary"].strip():
            raise AIServiceUnavailable("Gemini did not return an abstract_summary.")
        return data

    async def synthesize_meeting_mom(
        self,
        meeting_title: str,
        agendas: List[str],
        transcripts: List[Dict[str, Any]],
        language: str = "en",
    ) -> MinutesOfMeetingSchema:
        full_dialogue = "\n".join(
            f"[{item.get('speaker_label', 'Speaker')}]: {item.get('original_text', '')}"
            + (
                f" (Translation: {item.get('translated_text')})"
                if item.get("translated_text")
                else ""
            )
            for item in transcripts
        )
        if not full_dialogue.strip():
            raise AIServiceUnavailable("No transcript text is available for synthesis.")

        data = await self._generate_json(
            build_mom_prompt(meeting_title, agendas, transcripts, language=language)
        )
        try:
            return MinutesOfMeetingSchema(**data)
        except Exception as exc:
            raise AIServiceUnavailable(
                f"Gemini returned an invalid minutes structure: {exc}"
            ) from exc


gemini_service = GeminiService()
