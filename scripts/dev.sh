#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d backend/.venv ]]; then
  echo "backend/.venv not found. Run npm run setup first." >&2
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "frontend/node_modules not found. Run npm run setup first." >&2
  exit 1
fi

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from backend/.env.example."
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend on http://127.0.0.1:8000"
(
  cd backend
  # shellcheck source=/dev/null
  source .venv/bin/activate
  python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

echo "Starting React frontend on http://127.0.0.1:5173"
npm --prefix frontend run dev
