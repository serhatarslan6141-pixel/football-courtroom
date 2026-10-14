#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/.logs"
mkdir -p "$LOG_DIR"

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

cd "$FRONTEND_DIR"
nohup npm run dev -- --host 0.0.0.0 --port 5173 > "$LOG_DIR/frontend.log" 2>&1 &
printf '%s\n' $! > "$LOG_DIR/frontend.pid"

echo "Backend running on http://localhost:8000"
echo "Frontend running on http://localhost:5173"
