#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.logs"

for match_pattern in \
  'uvicorn app.main:app.*football-courtroom/backend.*--port 8000' \
  'vite --host 0.0.0.0 --port 5173'; do
  pid="$(pgrep -f "$match_pattern" | head -n 1 || true)"
  if [ -n "$pid" ]; then
    kill "$pid" || true
  fi
done

for file in "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid"; do
  if [ -f "$file" ]; then
    pid="$(cat "$file" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
    fi
    rm -f "$file"
  fi
done

echo "Stopped local Football Courtroom services."
