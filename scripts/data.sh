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
  *)
    echo "Usage: scripts/data.sh [init-db|download|index|bootstrap]" >&2
    echo "Environment: INDEX_LIMIT=5000 INDEX_BATCH_SIZE=128" >&2
    exit 1
    ;;
esac
