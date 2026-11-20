import json
from datetime import datetime
from typing import Any, Dict, List


def build_document_summary_prompt(title: str, text: str) -> str:
    return f"""
You are an institutional document intelligence engine for ACLEDA University of Business (AUB).
Analyze the following document and output valid JSON only.

Document Title: {title}
Document Content:
\"\"\"{text[:20000]}\"\"\"

Generate:
1. "abstract_summary": A formal, concise 150-250 word executive summary describing the purpose, scope, and key directives.
2. "entities": A JSON object containing signees, effective dates, responsible departments, and keywords.

Return ONLY raw JSON with keys "abstract_summary" and "entities".
"""


def build_mom_prompt(
    meeting_title: str,
    agendas: List[str],
    transcripts: List[Dict[str, Any]],
    current_date: str | None = None,
) -> str:
    current_date = current_date or datetime.utcnow().strftime("%Y-%m-%d")
    dialogue_lines = []
    for item in transcripts:
        speaker = item.get("speaker_label", "Speaker")
        original = item.get("original_text", "")
        translated = item.get("translated_text", "")
        dialogue_lines.append(
            f"[{speaker}]: {original}" + (f" (Translation: {translated})" if translated else "")
        )
    full_dialogue = "\n".join(dialogue_lines)

    return f"""
You are the AI Meeting Intelligence Assistant for ACLEDA University of Business (AUB).
Synthesize the following meeting dialogue into structured Minutes of Meeting (MoM).

Meeting Title: {meeting_title}
Current date: {current_date}
Scheduled Agendas: {json.dumps(agendas)}

Dialogue Transcripts:
\"\"\"{full_dialogue[:30000]}\"\"\"

Instructions:
1. Provide a comprehensive 150-250 word executive summary.
2. Isolate key discussion points per agenda.
3. Isolate formal decisions agreed upon by attendees.
4. Extract all actionable tasks. For each task, extract:
   - "task_description": Clear, specific task description.
   - "assignee_name": Name of responsible person if explicitly mentioned (otherwise null).
   - "deadline": Target date formatted as YYYY-MM-DD if mentioned (otherwise null). If no year is spoken, use the current year unless the context clearly indicates another year.
   - "confidence_score": Between 0.0 and 1.0.

Respond strictly in JSON matching the schema:
{{
  "meeting_title": "{meeting_title}",
  "executive_summary": "...",
  "discussion_points": ["point 1", "point 2"],
  "decisions": [
    {{"agenda_topic": "...", "decision_text": "...", "context_notes": "..."}}
  ],
  "action_items": [
    {{"task_description": "...", "assignee_name": "...", "deadline": "YYYY-MM-DD", "confidence_score": 0.95}}
  ]
}}
"""
