#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="$ROOT_DIR/backend/.venv"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required. Set PYTHON_BIN=/path/to/python if needed." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js/npm is required. Install Node 20+ and retry." >&2
  exit 1
fi

echo "Setting up backend virtual environment..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

if [[ "${1:-}" == "--optional" ]]; then
  echo "Installing optional local retrieval/NLP dependencies..."
  python -m pip install -r backend/requirements-optional.txt
else
  echo "Skipping optional Chroma/SentenceTransformers/SciSpaCy install."
  echo "Run scripts/setup.sh --optional if you need local embedding/corpus indexing."
fi

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from backend/.env.example."
fi

echo "Installing frontend dependencies..."
npm --prefix frontend install

echo
echo "Setup complete."
echo "Run: npm run dev"
echo "Frontend: http://127.0.0.1:5173"
echo "Backend:  http://127.0.0.1:8000"
