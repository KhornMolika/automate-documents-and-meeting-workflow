# ACLEDA University Document & Meeting Workflow

An AI-assisted document and meeting management system for **ACLEDA University of Business (AUB)**, Faculty of Science & Technology.

The app turns a meeting recording or transcript into reviewed, published minutes. Published minutes are archived in the document repository, and their action items and decisions become trackable follow-ups.

Live meeting capture is intentionally **not** part of this build. Meeting content is added as a recording, a direct file link, or a transcript.

---

## Architecture

```
backend/          FastAPI, SQLAlchemy 2.0, Pydantic v2
  api/v1/         auth, dashboard, documents, meetings, tasks, workspace exports
  models/         users, departments, documents, meetings, transcripts, summaries, tasks
  services/       transcript parser, transcription jobs, minutes archive, LLM, exports
  tests/          pytest suite
frontend/         Nuxt 3, Vue 3, shadcn-vue, Tailwind CSS
speech-service/   Local batch Khmer/English ASR and optional translation
docker-compose.yml
```

## Input paths

| Source | What happens |
|---|---|
| Upload a recording (`.mp3`, `.m4a`, `.wav`, `.mp4`, `.webm`, `.ogg`, `.aac`, `.flac`, `.mov`) | Saved locally, then transcribed in the background by the on-premise speech service |
| Paste a direct link | Downloaded with size and SSRF checks, then transcribed or parsed |
| Upload or paste a transcript (`.txt`, `.vtt`, `.srt`, `.docx`) | Parsed deterministically into speaker segments |
| Type the minutes | Fully manual, no AI required |

## Meeting workflow

1. Create a meeting and add an agenda.
2. Open the meeting and choose **Add content**.
3. Add a recording, link, or transcript.
4. Correct the transcript where needed, including speaker names.
5. Optionally generate an AI draft, or write the minutes directly.
6. Publish. This single action:
   - verifies the minutes
   - writes the official DOCX and action-item CSV
   - archives a copy in **Documents** under *Minutes of Meeting*
   - activates the action items and decisions in **Tasks**

## Pages

- **Overview** — next meeting, open/overdue tasks, recent documents
- **Meetings** — create meetings, add content, review and publish minutes
- **Documents** — repository, uploads, search, archived minutes
- **Tasks** — action items with status tracking and a read-only decision log

---

## Authentication

- Sign-in uses a **60-minute access token** and a **7-day refresh token**.
- The frontend refreshes the access token silently before it expires, so users are not logged out mid-task.
- If refresh fails, the app redirects to `/login` with a session-expired message and returns the user to the requested page after sign-in.
- Public registration is disabled. An administrator must create accounts through `POST /api/v1/auth/register`.
- Refresh tokens cannot be used as access tokens.
- Failed sign-in attempts are throttled: 5 failures per email and IP in 5 minutes, then `429` with `Retry-After`.
- Change `SECRET_KEY` and the seeded administrator password before deploying.

---

## Quick start

### 1. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API reference: `http://localhost:8000/docs`
- Default administrator: `admin@aub.edu.kh` / `Admin@AUB2026`
- SQLite is used by default (`backend/aub_workflow.db`). Set `DATABASE_URL` for PostgreSQL.

### 2. Speech service (Khmer ASR)

```bash
cd speech-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# ffmpeg must be installed (macOS: brew install ffmpeg)
uvicorn service:app --port 8001
```

For better Khmer accuracy, create `speech-service/.env` from `.env.example` and add a Google AI Studio key:

```bash
cd speech-service
cp .env.example .env
# edit .env and set GEMINI_API_KEY=...
```

With a key configured, Khmer segments are transcribed by Google's `gemini-3.5-transcribe` model, which is materially more accurate on Khmer script than the local CTC model. Without a key, the local Khmer ASR model is used instead. English always uses local faster-whisper.

- Khmer audio is sent to Google only when `GEMINI_API_KEY` is set.
- The local Khmer/English models download on first use and are cached.
- Khmer-to-English translation uses MyMemory and can be disabled with `translate=false`; the app requests translation so the optional MoM draft can use English text.
- If port 8001 is already in use, run the speech service on another port and set `SPEECH_SERVICE_URL` for the backend, e.g. `SPEECH_SERVICE_URL=http://127.0.0.1:8002`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Web app: `http://localhost:3000`

### 4. Docker

```bash
docker compose up --build
```

This starts PostgreSQL, the speech service, and the backend. The GPU speech image already includes ffmpeg.

---

## Optional AI minutes draft

The transcript and manual editor work without any model. **Generate draft** is optional and provider-agnostic:

```bash
LLM_PROVIDER=auto|gemini|ollama|opencode
GEMINI_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OPENCODE_API_KEY=...
```

If the provider is unavailable, the API returns an actionable error and the UI shows it; no draft is invented.

The AI output is always a draft. Only the version a human reviews and publishes becomes official.

## Correctness and privacy

- Transcript parsing, archiving, task tracking, overdue calculation and exports are deterministic.
- Transcription is probabilistic. The project's locally evaluated Khmer model reports **16.4% WER** on Khmer-English code-switching, and Google transcription can still mishear words. The review step exists because recognition is not perfect.
- English ASR and the local Khmer fallback run on campus. When `GEMINI_API_KEY` is configured, Khmer audio is sent to Google for transcription; Khmer-to-English translation uses MyMemory.
- Published minutes are the only source for the document archive, action items and decisions.

## Tests

```bash
cd backend
.venv/bin/python -m pytest tests -q
```

```bash
cd frontend
npm run test:e2e        # UI and API flows; live AI/ASR tests skipped
npm run test:e2e:live   # real Khmer + English recordings, Gemini transcription and AI drafts
```

The default Playwright suite runs against the real backend at `http://localhost:8000` and uses Chrome. The live suite additionally requires:

- the speech service on `SPEECH_SERVICE_URL` (default `http://localhost:8001`)
- `GEMINI_API_KEY` in `speech-service/.env` for Khmer transcription
- `GEMINI_API_KEY` in `backend/.env` for AI minutes and document summaries
- `DEMO_DIR` pointing to the demo files (default `/Users/alexkgm/Desktop/demo`)

The live suite covers:
- Khmer recording → Google transcription
- English recording → local faster-whisper
- AI minutes draft with source transcript
- AI document summary

## Known limitations

- No live meeting bot and no Chrome extension. Recordings must be uploaded or linked.
- Google Meet's saved transcripts support English and seven other languages, **not Khmer**. Khmer meetings need the local speech service or an external Khmer transcription tool.
- No speaker diarization. Every ASR segment starts as “Speaker”; speaker names can be corrected in the transcript editor.
- Long Khmer recordings on CPU can take several minutes. The job runs in the background and the page reports progress.
- Zoom/Teams share pages are HTML pages, not direct files. Download the recording or transcript before uploading.
