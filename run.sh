#!/usr/bin/env bash
#
# Start the complete ACLEDA Document & Meeting Workflow locally.
#
# Usage:
#   ./run.sh
#   BACKEND_PORT=8010 FRONTEND_PORT=3010 SPEECH_PORT=8012 ./run.sh
#   SKIP_SPEECH=1 ./run.sh          # transcript upload only, no local ASR
#   OPEN_BROWSER=0 ./run.sh         # do not open the browser automatically
#
# The script is idempotent: if a service is already healthy on its port, it is
# reused instead of being started twice. Press Ctrl+C to stop the services that
# this script started.

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOG_DIR="$ROOT/logs"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
SPEECH_PORT="${SPEECH_PORT:-8002}"
HOST="${HOST:-127.0.0.1}"
OPEN_BROWSER="${OPEN_BROWSER:-1}"
SKIP_SPEECH="${SKIP_SPEECH:-0}"

BACKEND_URL="http://${HOST}:${BACKEND_PORT}"
FRONTEND_URL="http://${HOST}:${FRONTEND_PORT}"
SPEECH_URL="http://${HOST}:${SPEECH_PORT}"

PIDS=()
NAMES=()

say()  { printf '\033[1;35m[run]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[run]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[run]\033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
  local code=$?
  trap - EXIT INT TERM

  if ((${#PIDS[@]})); then
    echo
    say "Stopping local services…"
    for pid in "${PIDS[@]}"; do
      pkill -TERM -P "$pid" 2>/dev/null || true
      kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in "${PIDS[@]}"; do
      for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
      done
      kill -KILL "$pid" 2>/dev/null || true
    done
  fi

  exit "$code"
}
trap cleanup EXIT INT TERM

port_busy() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1
}

probe() {
  local url=$1 pattern=$2
  local body
  body="$(curl -fsSL --max-time 3 "$url" 2>/dev/null)" || return 1
  if [[ -n "$pattern" ]]; then
    grep -qi -- "$pattern" <<<"$body" || return 1
  fi
  return 0
}

pick_python() {
  local candidate
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

ensure_python_env() {
  local dir=$1 name=$2
  if [[ -x "$dir/.venv/bin/python" ]]; then
    say "$name environment ready"
    return
  fi

  say "Creating $name virtual environment…"
  "$PYTHON_BIN" -m venv "$dir/.venv"
  "$dir/.venv/bin/python" -m pip install --upgrade pip >/dev/null
  "$dir/.venv/bin/pip" install -r "$dir/requirements.txt"
}

ensure_frontend_deps() {
  if [[ -x "$ROOT/frontend/node_modules/.bin/nuxt" ]]; then
    say "Frontend dependencies ready"
    return
  fi

  say "Installing frontend dependencies…"
  (
    cd "$ROOT/frontend"
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
  )
}

ensure_env_files() {
  if [[ ! -f "$ROOT/backend/.env" ]]; then
    say "Creating backend/.env for local SQLite…"
    local secret
    secret="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(48))')"
    cat > "$ROOT/backend/.env" <<EOF
APP_ENV=development
DEBUG=True
SECRET_KEY=$secret
DATABASE_URL=sqlite+aiosqlite:///./aub_workflow.db
DATABASE_URL_SYNC=sqlite:///./aub_workflow.db
LLM_PROVIDER=auto
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.1-flash-lite
SPEECH_SERVICE_URL=$SPEECH_URL
EOF
  fi

  if [[ ! -f "$ROOT/speech-service/.env" ]]; then
    cp "$ROOT/speech-service/.env.example" "$ROOT/speech-service/.env"
  fi

  if ! grep -Eq '^GEMINI_API_KEY=.+' "$ROOT/backend/.env" 2>/dev/null; then
    warn "No Gemini key found in backend/.env — AI minutes drafts are disabled."
    warn "Add GEMINI_API_KEY to backend/.env to enable them."
  fi
}

wait_for_service() {
  local name=$1 url=$2 pid=$3 log=$4
  local attempt

  for attempt in $(seq 1 180); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo
      tail -n 30 "$log" >&2 || true
      fail "$name exited before it became ready. See $log"
    fi

    if probe "$url" ""; then
      say "$name is ready"
      return 0
    fi

    if ((attempt % 15 == 0)); then
      say "Waiting for $name… (${attempt}s)"
    fi
    sleep 1
  done

  echo
  tail -n 30 "$log" >&2 || true
  fail "$name did not become ready in time. See $log"
}

reuse_or_start() {
  local name=$1 port=$2 health_url=$3 health_pattern=$4

  if port_busy "$port"; then
    if probe "$health_url" "$health_pattern"; then
      say "$name is already running at ${health_url%/*} — reusing it"
      return 1
    fi
    fail "Port $port is already used by another process. Stop it or choose a different port."
  fi

  return 0
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '/^# Usage:/,/^# this script started/p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

mkdir -p "$LOG_DIR"

command -v curl >/dev/null 2>&1 || fail "curl is required."
command -v lsof >/dev/null 2>&1 || fail "lsof is required."
command -v npm >/dev/null 2>&1 || fail "Node.js/npm is required."
PYTHON_BIN="$(pick_python)" || fail "Python 3.11+ is required."
command -v ffmpeg >/dev/null 2>&1 || warn "ffmpeg is missing — local recording transcription will fail."

if [[ "$SKIP_SPEECH" != "1" ]]; then
  ensure_python_env "$ROOT/speech-service" "Speech service"
fi
ensure_python_env "$ROOT/backend" "Backend"
ensure_frontend_deps
ensure_env_files

# ---------------------------------------------------------------------------
# Speech service
# ---------------------------------------------------------------------------
if [[ "$SKIP_SPEECH" == "1" ]]; then
  say "Skipping the speech service (SKIP_SPEECH=1)"
elif reuse_or_start "Speech service" "$SPEECH_PORT" "$SPEECH_URL/health" "Khmer ASR"; then
  say "Starting speech service on $SPEECH_URL"
  (
    cd "$ROOT/speech-service"
    exec "$ROOT/speech-service/.venv/bin/uvicorn" service:app \
      --host "$HOST" --port "$SPEECH_PORT"
  ) >"$LOG_DIR/speech.log" 2>&1 &
  service_pid=$!
  PIDS+=("$service_pid")
  NAMES+=("speech")
  wait_for_service "Speech service" "$SPEECH_URL/health" "$service_pid" "$LOG_DIR/speech.log"
fi

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
if reuse_or_start "Backend" "$BACKEND_PORT" "$BACKEND_URL/health" "ACLEDA"; then
  say "Starting backend on $BACKEND_URL"
  (
    cd "$ROOT/backend"
    exec env SPEECH_SERVICE_URL="$SPEECH_URL" \
      "$ROOT/backend/.venv/bin/uvicorn" app.main:app \
      --host "$HOST" --port "$BACKEND_PORT"
  ) >"$LOG_DIR/backend.log" 2>&1 &
  service_pid=$!
  PIDS+=("$service_pid")
  NAMES+=("backend")
  wait_for_service "Backend" "$BACKEND_URL/health" "$service_pid" "$LOG_DIR/backend.log"
fi

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
if reuse_or_start "Frontend" "$FRONTEND_PORT" "$FRONTEND_URL/login" "ACLEDA"; then
  say "Starting frontend on $FRONTEND_URL"
  (
    cd "$ROOT/frontend"
    exec env \
      NUXT_PUBLIC_API_BASE="$BACKEND_URL/api/v1" \
      NUXT_IGNORE_LOCK=1 \
      NUXT_TELEMETRY_DISABLED=1 \
      "$ROOT/frontend/node_modules/.bin/nuxt" dev \
      --host "$HOST" --port "$FRONTEND_PORT"
  ) >"$LOG_DIR/frontend.log" 2>&1 &
  service_pid=$!
  PIDS+=("$service_pid")
  NAMES+=("frontend")
  wait_for_service "Frontend" "$FRONTEND_URL/login" "$service_pid" "$LOG_DIR/frontend.log"
fi

cat <<EOF

  ACLEDA Document & Meeting Workflow

  App:      $FRONTEND_URL
  API:      $BACKEND_URL/docs
  Health:   $BACKEND_URL/health
  Logs:     $LOG_DIR
  Login:    admin@aub.edu.kh / Admin@AUB2026

  Press Ctrl+C to stop services started by this script.

EOF

if [[ "$OPEN_BROWSER" != "0" ]]; then
  if command -v open >/dev/null 2>&1; then
    open "$FRONTEND_URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
  fi
fi

if ((${#PIDS[@]} == 0)); then
  say "All services were already running."
  exit 0
fi

# Keep the script alive while it owns at least one service. If one dies, stop
# the rest and show the tail of its log.
while true; do
  for index in "${!PIDS[@]}"; do
    pid="${PIDS[$index]}"
    if ! kill -0 "$pid" 2>/dev/null; then
      name="${NAMES[$index]}"
      echo
      tail -n 40 "$LOG_DIR/$name.log" >&2 || true
      fail "$name stopped unexpectedly."
    fi
  done
  sleep 2
done
