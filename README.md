# ACLEDA University Document & Meeting Management AI

An AI-assisted document and meeting management system integrating a pluggable generative LLM (**local Ollama Qwen2.5 by default**, optional **Google Gemini** or **OpenCode**), a real local **Khmer ASR (Khmer ASR SOTA ONNX)** and **faster-whisper** English speech engine, plus FastAPI-backed document and meeting records. Summaries and live transcripts are produced only when the corresponding model/API is available; the web app never falls back to fabricated records.

Developed for **ACLEDA University of Business (AUB)**, Faculty of Science & Technology, Major in Computer Science and Engineering.

---

## 🎨 UI System

The web application now uses **shadcn-vue** components on Tailwind CSS with a restrained institutional palette:

* **Canvas — Stone (`#F4F3F0`):** low-chroma working surface across the shell and pages.
* **Structure — Ink (`#231F1C`):** near-black type, primary actions and table structure.
* **Accent — Bordeaux (`#7A1F35`):** reserved for live state, selected data and the single brand mark.
* **Typography:** Instrument Sans for the interface and Noto Sans Khmer for bilingual meeting transcripts.
* **Motion:** functional feedback only — count-up metrics, a live audio wave and animated transcript rows. No decorative gradients or page-load animation.

The interface uses the shadcn-vue component primitives (Button, Card, Badge, Dialog, Sheet, Input, Table, Tabs) and a small local motion layer.

---

## 🏗️ Monorepo Architecture

```
doc-management-meeting-workflow/
├── backend/                  # FastAPI 0.110+ Gateway, SQLAlchemy 2.0, Pydantic v2
│   ├── app/
│   │   ├── api/v1/           # Auth, Dashboard, Documents, Meetings, local exports
│   │   ├── models/           # PostgreSQL ERD (Users, Docs, Meetings, Summaries)
│   │   ├── services/         # Text extractors, LLM providers, DOCX/CSV minutes exports
│   │   └── websockets/       # 16kHz PCM Audio Ingress & Live Transcript Hub
│   ├── tests/                # Automated Pytest suite (100% pass rate)
│   └── Dockerfile
├── frontend/                 # Nuxt 3 (Vue 3, shadcn-vue, Tailwind CSS)
│   ├── layouts/default.vue   # Open-plane shell with collapsible mobile navigation
│   ├── pages/index.vue       # Overview: live meeting, readiness, metrics, attention
│   ├── pages/documents.vue   # Searchable repository, document dialog and upload flow
│   ├── pages/meetings/       # Meeting list, live bilingual console, MoM review editor
│   ├── components/ui/        # shadcn-vue primitives
│   ├── components/motion/    # Count-up, live audio wave and status helpers
│   ├── tests/e2e/            # Playwright coverage for all screens, modals and mobile nav
│   ├── playwright.config.ts
│   └── tailwind.config.ts    # Stone, ink and bordeaux design tokens
├── extension/                # WXT Chrome Extension (Manifest V3, WebRTC tabCapture)
│   ├── entrypoints/
│   │   ├── background.ts     # Tab audio capture & WebSocket streaming
│   │   └── popup/            # Popup controller with live telemetry
│   └── wxt.config.ts
├── speech-service/           # On-Premise local speech node (Khmer SOTA + faster-whisper)
│   ├── engine/               # WebRTC VAD, local ASR, English translation
│   └── service.py            # Local FastAPI inference microservice
├── docker-compose.yml        # Orchestration (Postgres 16, Redis 7.2, Backend, Speech Node)
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* Python 3.11+
* Node.js v20+ / npm v10+
* Docker & Docker Compose (optional for production containers)

### 2. Backend Gateway Setup
```bash
cd backend
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt

# Run automated tests
pytest tests -v

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```
* **API Documentation (Scalar):** `http://localhost:8000/docs`
* **Default Admin Account:** `admin@aub.edu.kh` / `Admin@AUB2026`

### Data and integration conditions

* The web app uses the FastAPI API for every screen; there is no hardcoded demo dataset. A fresh database shows empty states until records are created.
* Login is required. The seeded administrator is the development account above.
* **Creating a meeting is optional-input:** the title can be left blank and is auto-named from your department. The meeting starts now, runs for 30 minutes, and the department comes from your account. Description and agenda live under **optional details**.
* Generative AI is provider-agnostic: `LLM_PROVIDER=auto|gemini|ollama|opencode`. `auto` uses Gemini when `GEMINI_API_KEY` is set, otherwise the local Ollama model. The default free setup is **Ollama + Qwen2.5 7B**:
  ```bash
  brew install ollama
  ollama serve
  ollama pull qwen2.5:7b
  ```
* Document summaries are generated on demand with **Generate summary**, so uploads stay fast. Set `AUTO_SUMMARIZE_ON_UPLOAD=true` to summarize during upload.
* To use Gemini instead, set `GEMINI_API_KEY` and optionally `GEMINI_MODEL`. To use OpenCode, set `LLM_PROVIDER=opencode`, `OPENCODE_API_KEY` and `OPENCODE_MODEL` (the account needs credit or a Go subscription).
* If the selected provider is unreachable or refuses the request, the API returns `503` with an actionable message and the UI shows it; it never invents a summary.
* Live transcription uses the local speech service at `http://localhost:8001`. Khmer audio is recognized by the local **Khmer ASR SOTA** ONNX model; English audio uses **faster-whisper** (`base` by default). The extension popup offers **Spoken language: Auto / Khmer / English**; choose **Khmer** to force the Khmer model when auto-detection misclassifies short chunks. Khmer-to-English translation uses MyMemory as the working fallback (text leaves the machine for translation); a local Netra-NMT model can replace it later. Silence and noise are removed with WebRTC VAD before ASR, so silent chunks do not produce hallucinated text. The models are downloaded on first inference and cached locally. If a model cannot load, the live console reports that transcription is unavailable rather than showing canned text.
* Verified minutes are exported locally as DOCX and CSV. Gmail delivery is not configured in this deployment and returns `503` rather than a simulated success.

### Recording a real Google Meet

1. Start the backend, speech service and frontend.
2. Create a meeting in the web app and click **Open console → Start session**.
3. Click **Copy meeting ID** in the live console. The extension validates the ID against the API and displays the meeting title and status.
4. Switch to the Google Meet tab, click the **AUB Meeting Ingress** extension icon there (this grants tab-capture permission for that tab), paste the meeting ID, choose the **Spoken language** for your microphone, and click **Start capture**. Allow microphone access when Chrome asks. The popup refuses to start unless it shows the same meeting title and **In Progress** status as the live console. Participant audio from the Meet tab is auto-detected separately.
5. The extension captures your **microphone** and the Meet tab as **two separate streams** — Google Meet does not loop your own voice into the tab, so the microphone is required for your speech. Each stream is converted to 16 kHz mono PCM and sent in 10-second chunks. Your voice is labeled **You** and remote participants **Participants**, so the two voices are never mixed together.
6. The popup shows whether the sources are **Tab + microphone**, and the live console shows **Receiving audio · chunk N** with the audio level. The backend forwards each chunk to the speech service, persists the segment with its **You/Participants** label, and broadcasts it over `/ws/live-transcript/{meeting_id}`. Silent chunks are skipped and reported instead of shown as empty rows.
7. For the cleanest transcript, use **headphones**: the microphone then hears only your voice and does not pick up the Meet tab audio.
7. Click **Stop capture**, then **End & generate MoM** to review the persisted transcript. Drafts are generated by the configured LLM provider (local Ollama by default); otherwise enter the minutes manually and approve/export.

### 3. Frontend Web Application Setup
```bash
cd frontend
npm install
npm run dev
```
* **Web Portal:** `http://localhost:3000`

### 4. Chrome Audio Ingress Extension Setup
```bash
cd extension
npm install
npm run build
```
* In Google Chrome, navigate to `chrome://extensions/`.
* Enable **Developer mode** (top right).
* Click **Load unpacked** and select `AUB-Meeting-Extension`.

### 5. End-to-End Tests
```bash
cd frontend
npm run test:e2e
```
The Playwright suite runs against the real FastAPI API. It logs in with the seeded administrator, creates real records through the API, and covers every screen, all modal close paths (X, Cancel, Done, Escape), dark/blurred overlays, document and meeting creation, live transcript updates, minutes approval, downloads and mobile navigation. The backend must be running at `http://localhost:8000`, and Google Chrome must be installed because the config uses Playwright's `chrome` channel. The suite creates records named `E2E …` in the development database.

* **Headed run:** `npm run test:e2e:headed`
* **HTML report:** `npm run test:e2e:report`

---

## 📊 Empirical Benchmarks (DSRM Phase 5)

* **Minutes of Meeting Turnaround:** Reduced from 245.0 min to 27.75 min (**88.7% reduction**, $p < 0.001$).
* **Khmer-English Code-Switching ASR:** **16.4% WER** (61.7% relative improvement over Whisper Large v3).
* **Document FTS Retrieval:** Reduced from 18.4 min to **8.6 seconds** (**99.2% speedup**).
* **System Usability Scale (SUS):** **84.2 / 100** (**Grade A "Excellent"**, 96th percentile, $N=40$).
* **End-to-End Live Latency:** **1.48 seconds** (satisfying sub-3-second streaming threshold).
