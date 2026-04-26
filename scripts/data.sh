#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d backend/.venv ]]; then
  echo "backend/.venv not found. Run npm run setup first." >&2
  exit 1
fi

# shellcheck source=/dev/null
source backend/.venv/bin/activate

COMMAND="${1:-bootstrap}"
INDEX_LIMIT="${INDEX_LIMIT:-5000}"
INDEX_BATCH_SIZE="${INDEX_BATCH_SIZE:-128}"

case "$COMMAND" in
  init-db)
    (
      cd backend
      python - <<'PY'
from app.services.protocol_db import init_protocol_tables

init_protocol_tables()
print("SQLite tables are ready.")
PY
    )
    ;;
  download)
    (
      cd backend
      python -m app.scripts.download_grounding_datasets
    )
    ;;
  index)
    (
      cd backend
      python -m app.scripts.index_corpus_embeddings \
        --limit "$INDEX_LIMIT" \
        --batch-size "$INDEX_BATCH_SIZE"
    )
    ;;
  bootstrap)
    "$0" init-db
    "$0" download
    "$0" index
    ;;
  status)
    (
      cd backend
      python - <<'PY'
import json
from pathlib import Path

paths = {
    "sqlite": Path("app/data/ai_scientist.sqlite3"),
    "curated_corpus": Path("app/data/grounding_corpus/curated_protocol_examples.json"),
    "corpus_manifest": Path("app/data/grounding_corpus/corpus_manifest.json"),
    "embedding_manifest": Path("app/data/grounding_corpus/corpus_embedding_manifest.json"),
    "chroma_seed": Path("app/data/chroma_seed/chroma.sqlite3"),
    "runtime_chroma": Path("app/data/chroma/chroma.sqlite3"),
}
for name, path in paths.items():
    print(f"{name}: {'present' if path.exists() else 'missing'} {path}")
if paths["corpus_manifest"].exists():
    manifest = json.loads(paths["corpus_manifest"].read_text())
    print(f"curated_examples_total: {manifest.get('curated_examples_total')}")
if paths["embedding_manifest"].exists():
    manifest = json.loads(paths["embedding_manifest"].read_text())
    print(f"indexed_examples: {manifest.get('indexed_examples')}")
    print(f"embedding_model: {manifest.get('embedding_model')}")
PY
    )
    ;;
  *)
    echo "Usage: scripts/data.sh [init-db|download|index|bootstrap|status]" >&2
    echo "Environment: INDEX_LIMIT=5000 INDEX_BATCH_SIZE=128" >&2
    exit 1
    ;;
esac
