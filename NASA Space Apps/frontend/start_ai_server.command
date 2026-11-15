#!/bin/bash
# Start the shared backend so the frontend uses the reviewed PSI graph and
# allowlisted thermo functions. Set THERMO_PLANNER=api plus OPENAI_API_KEY and
# OPENAI_MODEL to use API inference; otherwise the cached local model is used.
FRONTEND_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$FRONTEND_DIR/../.." && pwd)"
cd "$PROJECT_ROOT" || exit 1
PORT="${PORT:-8015}"
export AI_PROVIDER=thermo
export THERMO_PLANNER="${THERMO_PLANNER:-local}"
export THERMO_SEMANTIC="${THERMO_SEMANTIC:-true}"
export PORT
if [ ! -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  echo "Project environment not found at $PROJECT_ROOT/.venv. Run uv sync --extra search first."
  exit 1
fi
"$PROJECT_ROOT/.venv/bin/python" "$FRONTEND_DIR/standin/server.py"
