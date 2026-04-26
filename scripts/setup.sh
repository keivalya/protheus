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

MODE="${1:-}"

if [[ "$MODE" == "--optional" || "$MODE" == "--full" ]]; then
  echo "Installing optional local retrieval/NLP dependencies..."
  python -m pip install -r backend/requirements-optional.txt
else
  echo "Skipping optional Chroma/SentenceTransformers/SciSpaCy install."
  echo "Run npm run setup:full if you need bundled Chroma/corpus retrieval."
fi

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from backend/.env.example."
fi

echo "Initializing local SQLite database..."
(
  cd backend
  python - <<'PY'
from app.services.protocol_db import init_protocol_tables

init_protocol_tables()
print("SQLite tables are ready.")
PY
)

echo "Installing frontend dependencies..."
npm --prefix frontend install

if [[ "$MODE" == "--full" ]]; then
  echo "Checking bundled corpus and embedding index..."
  (
    cd backend
    python - <<'PY'
import shutil
from pathlib import Path

seed_chroma = Path("app/data/chroma_seed")
runtime_chroma = Path("app/data/chroma")
required = [
    Path("app/data/grounding_corpus/curated_protocol_examples.json"),
    Path("app/data/grounding_corpus/corpus_manifest.json"),
    Path("app/data/grounding_corpus/corpus_embedding_manifest.json"),
    seed_chroma / "chroma.sqlite3",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(
        "Bundled retrieval data is missing: "
        + ", ".join(missing)
        + ". Run npm run data:bootstrap to rebuild it."
    )
if not (runtime_chroma / "chroma.sqlite3").exists():
    runtime_chroma.parent.mkdir(parents=True, exist_ok=True)
    if runtime_chroma.exists():
        shutil.rmtree(runtime_chroma)
    shutil.copytree(seed_chroma, runtime_chroma)
    print("Copied bundled Chroma seed index into local runtime storage.")
else:
    print("Local runtime Chroma index is already present.")
print("Bundled corpus and seed Chroma index are present.")
PY
  )
fi

echo
echo "Setup complete."
echo "Run: npm run dev"
echo "Frontend: http://127.0.0.1:5173"
echo "Backend:  http://127.0.0.1:8000"
