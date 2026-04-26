# Protheus Installation Guide

This guide is written for a human developer or an LLM coding agent installing Protheus from a fresh machine. Follow the commands in order and verify each checkpoint before moving on.

## 1. What This Installs

Protheus has two local services:

- FastAPI backend on `http://127.0.0.1:8000`
- React/Vite frontend on `http://127.0.0.1:5173`

The complete install also includes local retrieval data:

- Curated protocol corpus: `backend/app/data/grounding_corpus/`
- Seed Chroma embedding index: `backend/app/data/chroma_seed/`
- Runtime Chroma index copied at setup time: `backend/app/data/chroma/`
- Runtime SQLite database created locally: `backend/app/data/ai_scientist.sqlite3`

The seed index is committed, but runtime `chroma/` is ignored because Chroma mutates its SQLite files during use.

## 2. Prerequisites

Required:

```text
Git
Python 3.10 or 3.11
Node.js 20+
npm
bash-compatible shell
```

Recommended:

```text
macOS, Linux, or Windows with WSL
5 GB free disk space minimum
8 GB free disk space recommended for optional NLP packages
```

Check versions:

```bash
git --version
python3 --version
node --version
npm --version
bash --version
```

Expected:

- Python should be `3.10.x` or `3.11.x`.
- Node should be `20.x` or newer.
- `npm` should be available on `PATH`.

## 3. Clone The Repository

Use the working branch until it is merged into `main`:

```bash
git clone https://github.com/keivalya/protheus.git
cd protheus
git checkout codex/ai-scientist-import
```

Verify:

```bash
git status --short --branch
```

Expected:

```text
## codex/ai-scientist-import...origin/codex/ai-scientist-import
```

## 4. Complete Install With Data And Embeddings

Run:

```bash
npm run setup:full
```

This does all of the following:

- Creates `backend/.venv`
- Installs backend dependencies from `backend/requirements.txt`
- Installs optional retrieval dependencies from `backend/requirements-optional.txt`
- Creates `backend/.env` from `backend/.env.example` if missing
- Initializes local SQLite tables
- Installs frontend dependencies
- Verifies bundled corpus files
- Copies `backend/app/data/chroma_seed/` to `backend/app/data/chroma/` if runtime Chroma does not already exist

Expected final lines:

```text
Bundled corpus and seed Chroma index are present.
Setup complete.
Run: npm run dev
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
```

## 5. Environment Variables

Open:

```bash
$EDITOR backend/.env
```

The app can run with demo fallbacks, but the best results use these values:

```text
OPENALEX_MAILTO=you@example.com
PROTOCOLS_IO_TOKEN=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
OPENAI_PROTOCOL_MODEL=gpt-5.1
OPENAI_PROTOCOL_REASONING_EFFORT=medium
OPENAI_PROTOCOL_MAX_COMPLETION_TOKENS=12000
SCISPACY_MODEL=en_core_sci_sm
USE_MOCK_PROTOCOLS=false
AI_SCIENTIST_DB_PATH=
AI_SCIENTIST_CHROMA_PATH=
AI_SCIENTIST_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Rules:

- Do not commit `backend/.env`.
- Do not paste API keys into source files, README files, issue comments, or commit messages.
- If no `OPENAI_API_KEY` is available, the app still runs but LLM-backed generation quality will be limited by fallbacks.

## 6. Verify Data And Embeddings

Run:

```bash
npm run data:status
```

Expected:

```text
sqlite: present app/data/ai_scientist.sqlite3
curated_corpus: present app/data/grounding_corpus/curated_protocol_examples.json
corpus_manifest: present app/data/grounding_corpus/corpus_manifest.json
embedding_manifest: present app/data/grounding_corpus/corpus_embedding_manifest.json
chroma_seed: present app/data/chroma_seed/chroma.sqlite3
runtime_chroma: present app/data/chroma/chroma.sqlite3
curated_examples_total: 5000
indexed_examples: 5000
embedding_model: sentence-transformers/all-MiniLM-L6-v2
```

Optional embedding retrieval smoke test:

```bash
cd backend
source .venv/bin/activate
python - <<'PY'
from app.services.corpus_retriever import query_corpus_embedding_examples

hypothesis = {
    "domain": "cell_biology",
    "model_system": "hiPSC organoids",
    "intervention": "cortical striatal organoid fusion assembloid",
    "outcome": "inter-regional connectivity",
    "keywords": ["hiPSC", "organoids", "assembloids", "cortical", "striatal", "fusion"],
}
results = query_corpus_embedding_examples(hypothesis, limit=3)
print(f"embedding_results={len(results)}")
for result in results:
    print(result.id, result.source, result.search_backend, result.score)
PY
cd ..
```

Expected:

```text
embedding_results=3
```

The exact result IDs and scores can vary, but `search_backend` should include `chroma_embeddings`.

## 7. Start The App

Run both services:

```bash
npm run dev
```

Expected:

```text
Starting FastAPI backend on http://127.0.0.1:8000
Starting React frontend on http://127.0.0.1:5173
```

Open:

```text
http://127.0.0.1:5173
```

Backend health check from a second terminal:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected:

```json
{"status":"ok"}
```

Corpus stats check:

```bash
curl http://127.0.0.1:8000/api/protocol-corpus/stats
```

Expected fields:

```text
curated_examples_total
embedding_index
sources
```

## 8. Build Verification

Backend syntax check:

```bash
backend/.venv/bin/python -m compileall -q backend/app
```

Frontend production build:

```bash
npm run build
```

Expected:

- TypeScript build passes.
- Vite build completes.
- A chunk-size warning for `html2pdf` is acceptable.

## 9. Lightweight Install

Use this only when local embedding retrieval is not needed:

```bash
npm run setup
npm run dev
```

This skips optional Chroma/SentenceTransformers/SciSpaCy dependencies. The app runs, but local embedding retrieval may fall back to deterministic ranking or return fewer retrieval results.

## 10. Rebuild Data From Sources

The repository already includes the current corpus and seed embedding index. Rebuilding is optional.

To rebuild the local SQLite tables only:

```bash
npm run data:init
```

To re-download and re-curate the corpus:

```bash
npm run data:download
```

To rebuild the runtime Chroma embedding index:

```bash
npm run data:index
```

To run the full data bootstrap:

```bash
npm run data:bootstrap
```

Default indexing configuration:

```text
INDEX_LIMIT=5000
INDEX_BATCH_SIZE=128
```

Override example:

```bash
INDEX_LIMIT=5000 INDEX_BATCH_SIZE=64 npm run data:index
```

After rebuilding, run:

```bash
npm run data:status
```

## 11. Runtime Files And Git Safety

These files are generated locally and should stay uncommitted:

```text
backend/.env
backend/.venv/
frontend/node_modules/
backend/app/data/ai_scientist.sqlite3
backend/app/data/chroma/
backend/app/data/evaluations/
backend/app/data/observability/
frontend/dist/
```

Before committing changes:

```bash
git status --short
git diff --cached --check
git diff --cached --name-only | grep -E '(^|/)\\.env($|\\.)|ai_scientist\\.sqlite3|app/data/chroma/|OPENAI_API_KEY' || true
```

Expected:

- No `.env` files staged.
- No runtime SQLite database staged.
- No runtime `app/data/chroma/` files staged.
- No API keys staged.

## 12. Common Problems

### `python3` points to the wrong Python

Use:

```bash
PYTHON_BIN=/path/to/python3.11 npm run setup:full
```

### `backend/.venv not found`

Run setup first:

```bash
npm run setup:full
```

### `frontend/node_modules not found`

Run:

```bash
npm --prefix frontend install
```

or rerun:

```bash
npm run setup:full
```

### Port `8000` is already in use

Find the process:

```bash
lsof -i :8000
```

Stop it, then rerun:

```bash
npm run dev
```

### Port `5173` is already in use

Vite may choose another port automatically. If it does, use the URL printed in the terminal.

### Runtime Chroma index is missing

Run:

```bash
npm run setup:full
npm run data:status
```

If the seed index is missing too, rebuild:

```bash
npm run data:bootstrap
```

### Optional packages fail on Windows

Use WSL. The scripts assume a bash-compatible shell and are tested for macOS/Linux-style environments.

### OpenAI calls fail

Check:

```bash
grep -E '^OPENAI_' backend/.env
```

Confirm:

- `OPENAI_API_KEY` is set.
- The selected model is available to the key.
- Network access is available.

## 13. Expected Project Layout

Important paths:

```text
backend/app/main.py                         FastAPI entrypoint
backend/app/services/                       backend service modules
backend/app/services/protocol_orchestrator.py
backend/app/services/corpus_retriever.py
backend/app/services/protocol_generation.py
backend/app/services/protocol_validator.py
backend/app/data/grounding_corpus/          committed curated corpus
backend/app/data/chroma_seed/               committed seed embedding index
backend/app/data/chroma/                    local runtime embedding index
backend/app/data/validation_corpus/         committed validation corpus
frontend/src/                               React frontend
scripts/setup.sh                            setup script
scripts/dev.sh                              local dev launcher
scripts/data.sh                             data commands
```

## 14. Installation Checklist For An LLM Agent

Use this as the final checklist:

```text
[ ] Clone repo
[ ] Checkout codex/ai-scientist-import
[ ] Run npm run setup:full
[ ] Add backend/.env values if available
[ ] Run npm run data:status
[ ] Confirm 5000 curated examples
[ ] Confirm 5000 indexed examples
[ ] Confirm runtime_chroma is present
[ ] Run backend compile check
[ ] Run npm run build
[ ] Run npm run dev
[ ] Confirm frontend opens at http://127.0.0.1:5173
[ ] Confirm backend health returns {"status":"ok"}
[ ] Do not commit .env, runtime SQLite, runtime chroma, node_modules, or dist
```
