import json
import logging
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.schemas.meeting import MinutesOfMeetingSchema
from app.services.gemini_service import AIServiceUnavailable, gemini_service
from app.services.prompts import build_document_summary_prompt, build_mom_prompt

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> Dict[str, Any]:
    """Parse a JSON object from a model response, tolerating code fences or prose."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("The model did not return a JSON object.")
    return data


class LLMService:
    """Provider-agnostic generative LLM for summaries and minutes of meeting.

    Providers:
    - ``gemini``   Google Gemini through the official SDK (requires GEMINI_API_KEY).
    - ``ollama``   A local model through Ollama's HTTP API (no key, no billing).
    - ``opencode`` OpenCode's OpenAI-compatible inference endpoint (requires credit).
    """

    @property
    def provider(self) -> str:
        configured = (settings.LLM_PROVIDER or "auto").strip().lower()
        if configured in {"gemini", "ollama", "opencode"}:
            return configured
        if configured != "auto":
            logger.warning("Unknown LLM_PROVIDER=%s; using auto selection.", configured)
        if settings.GEMINI_API_KEY:
            return "gemini"
        return "ollama"

    @property
    def is_configured(self) -> bool:
        provider = self.provider
        if provider == "gemini":
            return gemini_service.is_configured
        if provider == "opencode":
            return bool(settings.OPENCODE_API_KEY)
        return bool(settings.OLLAMA_BASE_URL and settings.OLLAMA_MODEL)

    def describe(self) -> str:
        provider = self.provider
        if provider == "gemini":
            return f"Gemini ({settings.GEMINI_MODEL})"
        if provider == "opencode":
            return f"OpenCode ({settings.OPENCODE_MODEL})"
        return f"Ollama ({settings.OLLAMA_MODEL} at {settings.OLLAMA_BASE_URL})"

    async def _generate_ollama(self, prompt: str) -> str:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
        except httpx.ConnectError as exc:
            raise AIServiceUnavailable(
                f"Ollama is not reachable at {settings.OLLAMA_BASE_URL}. "
                "Start it with `ollama serve`."
            ) from exc
        except httpx.TimeoutException as exc:
            raise AIServiceUnavailable(
                f"Ollama timed out after {settings.OLLAMA_TIMEOUT_SECONDS}s while generating a response."
            ) from exc

        if response.status_code == 404:
            raise AIServiceUnavailable(
                f"Ollama model '{settings.OLLAMA_MODEL}' is not installed. "
                f"Run `ollama pull {settings.OLLAMA_MODEL}`."
            )
        if response.status_code != 200:
            raise AIServiceUnavailable(
                f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
            )
        content = ((response.json().get("message") or {}).get("content") or "").strip()
        if not content:
            raise AIServiceUnavailable("Ollama returned an empty response.")
        return content

    async def _generate_opencode(self, prompt: str) -> str:
        if not settings.OPENCODE_API_KEY:
            raise AIServiceUnavailable("OPENCODE_API_KEY is not configured.")
        url = f"{settings.OPENCODE_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENCODE_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "AUB-Workflow/1.0",
            "x-opencode-session": settings.OPENCODE_SESSION,
        }
        payload = {
            "model": settings.OPENCODE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise AIServiceUnavailable(
                f"OpenCode is not reachable at {settings.OPENCODE_BASE_URL}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise AIServiceUnavailable("OpenCode timed out while generating a response.") from exc

        if response.status_code != 200:
            message = response.text[:300]
            try:
                error = response.json().get("error") or {}
                message = error.get("message") or message
            except Exception:
                pass
            raise AIServiceUnavailable(
                f"OpenCode returned HTTP {response.status_code}: {message}"
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIServiceUnavailable("OpenCode returned an unexpected response.") from exc
        content = (content or "").strip()
        if not content:
            raise AIServiceUnavailable("OpenCode returned an empty response.")
        return content

    async def _generate_json(self, prompt: str) -> str:
        provider = self.provider
        if provider == "ollama":
            return await self._generate_ollama(prompt)
        if provider == "opencode":
            return await self._generate_opencode(prompt)
        raise AIServiceUnavailable(
            f"{self.describe()} does not support plain generation through _generate_json."
        )

    async def summarize_document(self, title: str, text: str) -> Dict[str, Any]:
        if not text.strip():
            raise AIServiceUnavailable("No extracted text is available to summarize.")
        if self.provider == "gemini":
            return await gemini_service.summarize_document(title, text)

        raw = await self._generate_json(build_document_summary_prompt(title, text))
        try:
            data = _extract_json(raw)
        except Exception as exc:
            raise AIServiceUnavailable(
                f"{self.describe()} returned an invalid summary: {exc}"
            ) from exc

        summary = data.get("abstract_summary")
        if not isinstance(summary, str) or not summary.strip():
            raise AIServiceUnavailable(f"{self.describe()} did not return an abstract_summary.")
        return data

    async def synthesize_meeting_mom(
        self,
        meeting_title: str,
        agendas: List[str],
        transcripts: List[Dict[str, Any]],
    ) -> MinutesOfMeetingSchema:
        has_text = any(
            (item.get("original_text") or item.get("translated_text") or "").strip()
            for item in transcripts
        )
        if not has_text:
            raise AIServiceUnavailable("No transcript text is available for synthesis.")
        if self.provider == "gemini":
            return await gemini_service.synthesize_meeting_mom(
                meeting_title, agendas, transcripts
            )

        raw = await self._generate_json(build_mom_prompt(meeting_title, agendas, transcripts))
        try:
            data = _extract_json(raw)
            return MinutesOfMeetingSchema(**data)
        except Exception as exc:
            raise AIServiceUnavailable(
                f"{self.describe()} returned an invalid MoM draft: {exc}"
            ) from exc


llm_service = LLMService()
