import json
import logging
from typing import Dict, Any, List
from app.core.config import settings
from app.schemas.meeting import MinutesOfMeetingSchema
from app.services.prompts import build_document_summary_prompt, build_mom_prompt

logger = logging.getLogger(__name__)


class AIServiceUnavailable(RuntimeError):
    """Raised when Gemini is not configured or cannot return a usable response."""


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self._client = None

        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model_name)
                logger.info("Gemini client initialized with model %s", self.model_name)
            except Exception as exc:
                logger.warning("Could not initialize Google Generative AI client: %s", exc)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    async def summarize_document(self, title: str, text: str) -> Dict[str, Any]:
        """
        Generate an executive abstract and structured entity tags.
        No fabricated fallback is returned: callers must handle AIServiceUnavailable.
        """
        if not self._client:
            raise AIServiceUnavailable("GEMINI_API_KEY is not configured.")
        if not text.strip():
            raise AIServiceUnavailable("No extracted text is available to summarize.")

        prompt = build_document_summary_prompt(title, text)
        try:
            response = self._client.generate_content(prompt)
            clean_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(clean_text)
            if not isinstance(data.get("abstract_summary"), str):
                raise ValueError("Gemini response did not contain abstract_summary.")
            return data
        except Exception as exc:
            logger.error("Gemini document summarization failed: %s", exc)
            raise AIServiceUnavailable(f"Gemini document summarization failed: {exc}") from exc

    async def synthesize_meeting_mom(
        self,
        meeting_title: str,
        agendas: List[str],
        transcripts: List[Dict[str, Any]],
    ) -> MinutesOfMeetingSchema:
        """
        Synthesize bilingual transcripts into structured minutes.
        No fabricated fallback is returned: callers must handle AIServiceUnavailable.
        """
        if not self._client:
            raise AIServiceUnavailable("GEMINI_API_KEY is not configured.")

        dialogue_lines = []
        for item in transcripts:
            speaker = item.get("speaker_label", "Speaker")
            original = item.get("original_text", "")
            translated = item.get("translated_text", "")
            dialogue_lines.append(
                f"[{speaker}]: {original}" + (f" (Translation: {translated})" if translated else "")
            )
        full_dialogue = "\n".join(dialogue_lines)
        if not full_dialogue.strip():
            raise AIServiceUnavailable("No transcript text is available for synthesis.")

        prompt = build_mom_prompt(meeting_title, agendas, transcripts)
        try:
            response = self._client.generate_content(prompt)
            clean_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(clean_text)
            return MinutesOfMeetingSchema(**data)
        except Exception as exc:
            logger.error("Gemini MoM synthesis failed: %s", exc)
            raise AIServiceUnavailable(f"Gemini MoM synthesis failed: {exc}") from exc


gemini_service = GeminiService()
