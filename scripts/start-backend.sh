#!/usr/bin/env bash
# Foreground backend only; no .env loading or live-mode overrides.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PYTHON="$(bash "$ROOT_DIR/scripts/backend-python.sh")"
echo "Backend interpreter: $BACKEND_PYTHON"
"$BACKEND_PYTHON" --version
exec "$BACKEND_PYTHON" -m uvicorn app.main:app --app-dir "$ROOT_DIR/backend" --host 127.0.0.1 --port 8000 "$@"
