<div align="center">

<img src="logo.png" alt="Protheus" width="120" />

# Protheus

**From hypothesis to a Monday-ready experiment plan, in minutes.**

<sub>Evidence-grounded protocol drafting, supplier-resolved materials, dependency-aware scheduling — with a researcher in the loop on every step.</sub>

<br />

![Backend](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-646CFF?logo=vite&logoColor=white)
![Language](https://img.shields.io/badge/language-Python%203.11%20%7C%20TypeScript-blue)
![Status](https://img.shields.io/badge/status-proof%20of%20concept-orange)

</div>

---

## The problem

Modern AI can generate drug-discovery hypotheses in minutes. Translating one into a runnable experiment still takes a senior scientist **weeks** of manual work — sourcing reagents, scrubbing protocols, scheduling instruments, justifying spend. A single back-ordered reagent or hallucinated concentration wastes the experiment and the capital behind it.

This is the **execution gap** between digital science and physical science.

## The solution

Protheus is a decision-support layer that turns scientific intent into a verifiable, executable plan. Three things happen end-to-end:

1. **Evidence-grounded mapping** — instead of inventing steps, Protheus surfaces proven methodologies from `protocols.io` and OpenAlex aligned to the user's hypothesis. The researcher selects one or several as the grounding template.
2. **Operational blueprinting** — protocol steps map to a phased Gantt with dependencies, a procurement-ready material manifest with real catalog numbers and lead times, and a budget that accounts for equipment booking and personnel time.
3. **Adaptive learning loop** — every researcher correction (preferred suppliers, on-site equipment, lab-specific quirks) is persisted as long-term memory and feeds the next draft. The system gets sharper with use.

## What makes it different

> **Protheus is the only platform that treats the execution gap as a first-class problem.** Discovery tools predict molecules; lab tools track inventory. Nothing in the middle ties hypothesis to bench with full provenance — until now.

Every step in a Protheus plan is **referenced**, **customizable**, and **auditable**. A draft is not the end state — it is a starting point a researcher can challenge, edit, and approve with the receipts in hand.

## Audience

| Role | What they currently do | What Protheus replaces it with |
| --- | --- | --- |
| **PIs / R&D leads** | Sign off on plans built in slide decks | A verifiable audit trail per budget line and protocol step |
| **Lab managers / procurement** | Days of spreadsheet sourcing | An automated manifest with catalog IDs and shipping lead times |
| **Bench scientists** | Lose days to scheduling and logistics | A dependency-mapped Gantt that respects physical constraints |

## Architecture

Protheus is a supervised multi-agent system, deliberately not a single-prompt LLM wrapper. Three stages, each with explicit trust boundaries between generative agents and deterministic services.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 1 — Deterministic Literature QC                                       │
│   Hypothesis → structured fields → OpenAlex + protocols.io + curated corpus  │
│   Scoring: BM25 + RapidFuzz + field-level match. No LLM in the novelty path. │
├──────────────────────────────────────────────────────────────────────────────┤
│  Stage 2 — Schema-Enforced Protocol Generation                               │
│   Multi-protocol grounding + Pydantic / Instructor schemas + validation gate │
│   Anchored in selected sources; refused outputs go back through revision.    │
├──────────────────────────────────────────────────────────────────────────────┤
│  Stage 3 — Operational Planning & Feedback                                   │
│   Material extraction → vendor resolution → budget + Gantt + funding routes  │
│   Researcher feedback persisted in ChromaDB as long-term memory.             │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Technology

| Layer | Stack |
| --- | --- |
| **Frontend** | React 18 · TypeScript · Vite · `html2pdf.js` (lazy-loaded) · Fraunces / DM Sans / IBM Plex Mono |
| **Backend** | FastAPI · Pydantic · Uvicorn · SQLite · `httpx` · OpenAI SDK |
| **Retrieval** | OpenAlex · `protocols.io` API + curated corpus · BM25 + RapidFuzz field-level matching · ChromaDB + sentence-transformers (optional) |
| **Operational planning** | Material extractor → product / image resolver → price estimator → budget calculator → timeline planner |
| **Storage** | SQLite for sessions, versions, feedback, transparency events, operational plans |

## Quickstart

**Backend** (Python 3.11 recommended):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend** (in a second terminal):

```bash
cd protheus
npm install
npm run dev
```

Open `http://prothe.us/`. The Vite dev server proxies `/api/*` to the FastAPI process at `127.0.0.1:8000`.

> On macOS, port 80 may require elevated permission. If `npm run dev` reports `EACCES: permission denied 0.0.0.0:80`, run `sudo npm run dev`.

Optional NLP / vector-retrieval dependencies live in `backend/requirements-optional.txt`. They are not required for the default run and are best installed with Python 3.10 or 3.11.

## Project layout

```
protheus/
├─ backend/
│  └─ app/
│     ├─ main.py                  FastAPI routes
│     ├─ services/
│     │  ├─ openalex.py           paper retrieval + curated references
│     │  ├─ protocols_io.py       protocol search + curated KNOWN_PROTOCOLS
│     │  ├─ query_expansion.py    hypothesis structuring + concept matching
│     │  ├─ qc.py                 deterministic novelty signal
│     │  ├─ protocol_orchestrator.py    schema-enforced draft generation
│     │  ├─ operational_plan.py   end-to-end plan compilation
│     │  ├─ material_extractor.py / product_resolver.py / image_resolver.py
│     │  ├─ price_estimator.py / budget_calculator.py / timeline_planner.py
│     │  └─ protocol_db.py        SQLite persistence
│     └─ data/                    mock protocols, validation rules
└─ frontend/
   └─ src/
      ├─ App.tsx                  5-step wizard
      ├─ components/FullPlan.tsx  7-tab plan view + PDF export
      ├─ lib/planMock.ts          plan template + operational-plan merger
      ├─ api.ts / types.ts        backend client + shared schemas
      └─ styles.css               CSS variables + print stylesheet
```

## Status

This is a working **proof of concept**. The end-to-end flow — query → literature QC → multi-protocol selection → researcher-review draft → operational plan with vendors, budget, timeline, and funding routes — runs locally against the bundled mock data and live OpenAlex / protocols.io when configured. Researcher feedback is captured; the long-term memory loop continues to mature with each iteration.

What the next phase aims for:

- **Lead-time compression** — target a 70% reduction in *hypothesis-to-bench* scoping time.
- **Continuous improvement** — every correction sharpens the next plan.
- **Trust-based adoption** — every line of every plan is referenced and overridable.

> *"While AI makes hypothesis generation effortless, the path to a concrete, executable plan remains a significant bottleneck. In a competitive research environment, this tool provides a decisive advantage by automating the logistical groundwork, allowing me to focus more on innovation and benchwork rather than administrative planning."*
> — PI, Biotech

---

<div align="center">
<sub>Built for researchers who want science at the speed of thought, without giving up the receipts.</sub>
</div>
