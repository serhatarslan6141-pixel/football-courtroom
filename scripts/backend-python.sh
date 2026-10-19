#!/usr/bin/env bash
# Resolve an installed Phase 4B runtime without reading .env or installing anything.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

is_ready() {
  [ -x "$1" ] || return 1
  "$1" - <<'PY' >/dev/null 2>&1
import sys
from importlib.metadata import version

if sys.version_info < (3, 12):
    raise SystemExit(1)
for name, expected in {
    'agent-framework-core': '1.22.0',
    'agent-framework-openai': '1.17.0',
    'openai': '2.48.0',
    'fastapi': '0.115.0',
    'uvicorn': '0.30.6',
}.items():
    if version(name) != expected:
        raise SystemExit(1)
PY
}

if [ -n "${FOOTBALL_BACKEND_PYTHON:-}" ]; then
  if is_ready "$FOOTBALL_BACKEND_PYTHON"; then
    printf '%s\n' "$FOOTBALL_BACKEND_PYTHON"
    exit 0
  fi
else
  for candidate in "$ROOT_DIR/.venv/phase4b/bin/python" "$ROOT_DIR/.venv/bin/python"; do
    if is_ready "$candidate"; then
      printf '%s\n' "$candidate"
      exit 0
    fi
  done
fi

echo "Backend requires Python 3.12+ and the pinned backend/requirements-agents.txt dependencies." >&2
echo "Prepare .venv/phase4b, or set FOOTBALL_BACKEND_PYTHON to a ready interpreter. See docs/phase4b.md." >&2
exit 1
