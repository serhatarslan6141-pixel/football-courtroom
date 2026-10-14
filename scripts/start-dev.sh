#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/.logs"
mkdir -p "$LOG_DIR"

kill_matching_pid() {
  local match_pattern="$1"
  local pid
  pid="$(pgrep -f "$match_pattern" | head -n 1 || true)"
  if [ -n "$pid" ]; then
    echo "Stopping stale process $pid for pattern: $match_pattern"
    kill "$pid" || true
    sleep 1
  fi
}

if command -v lsof >/dev/null 2>&1; then
  stale_backend_pid="$(lsof -nP -t -iTCP:8000 -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$stale_backend_pid" ]; then
    stale_backend_cmd="$(ps -p "$stale_backend_pid" -o command= 2>/dev/null || true)"
    if printf '%s' "$stale_backend_cmd" | grep -Eq 'uvicorn app\.main:app.*football-courtroom/backend.*--port 8000|Python.*uvicorn app\.main:app.*--port 8000'; then
      echo "Stopping stale backend on port 8000: $stale_backend_pid"
      kill "$stale_backend_pid" || true
      sleep 1
    fi
  fi
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --quiet -r "$BACKEND_DIR/requirements.txt"

nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --app-dir "$BACKEND_DIR" --host 0.0.0.0 --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
printf '%s\n' $! > "$LOG_DIR/backend.pid"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies"
  (cd "$FRONTEND_DIR" && npm install)
fi

if command -v lsof >/dev/null 2>&1; then
  stale_frontend_pid="$(lsof -nP -t -iTCP:5173 -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$stale_frontend_pid" ]; then
    stale_frontend_cmd="$(ps -p "$stale_frontend_pid" -o command= 2>/dev/null || true)"
    if printf '%s' "$stale_frontend_cmd" | grep -q 'vite'; then
      echo "Stopping stale frontend on port 5173: $stale_frontend_pid"
      kill "$stale_frontend_pid" || true
      sleep 1
    fi
  fi
fi

cd "$FRONTEND_DIR"
nohup npm run dev -- --host 0.0.0.0 --port 5173 > "$LOG_DIR/frontend.log" 2>&1 &
printf '%s\n' $! > "$LOG_DIR/frontend.pid"

echo "Backend running on http://localhost:8000"
echo "Frontend running on http://localhost:5173"
