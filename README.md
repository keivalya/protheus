<div align="center">

<img src="logo.png" alt="Protheus" width="120" />

# Protheus

**From hypothesis to a Monday-ready experiment plan, in minutes.**

<sub>Evidence-grounded protocol drafting, supplier-resolved materials, dependency-aware scheduling — with a researcher in the loop on every step.</sub>

<br />

[![Live at prothe.us](https://img.shields.io/badge/live%20at-prothe.us-7a2d2d?style=for-the-badge)](https://prothe.us)

</div>

---

## Run locally

Use this path on a teammate's laptop.

Prerequisites:

```text
Python 3.10 or 3.11 recommended
Node.js 20+
npm
```

Complete setup:

```bash
git clone https://github.com/keivalya/protheus.git
cd protheus
npm run setup:full
```

Add keys if available:

```bash
$EDITOR backend/.env
```

The app has fallbacks for demos, but these improve results:

```text
OPENAI_API_KEY=...
PROTOCOLS_IO_TOKEN=...
OPENALEX_MAILTO=you@example.com
```

Run both backend and frontend:

```bash
npm run dev
```

Open:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
```

Lightweight setup without optional local embedding libraries:

```bash
npm run setup
```

The repository includes the curated protocol corpus and a seed Chroma embedding index. `setup:full` installs the optional ChromaDB/SentenceTransformers/SciSpaCy dependencies and copies the seed index into local runtime storage. Use the lightweight setup only if you want the app to run with deterministic fallbacks and without local embedding retrieval.

Rebuild local retrieval data:

```bash
npm run data:bootstrap
```

That re-downloads the local grounding corpus and rebuilds the runtime Chroma embedding index. It is not required because the repo already includes the current curated corpus and seed embedding index.

Data commands:

```bash
npm run data:init       # create/update local SQLite tables
npm run data:download   # download and curate the local protocol corpus
npm run data:index      # build the Chroma embedding index
npm run data:status     # show local corpus/index state
```

Local runtime data is intentionally not committed:

```text
backend/app/data/ai_scientist.sqlite3
backend/app/data/chroma/
backend/app/data/evaluations/
backend/app/data/observability/
```

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

---

> *"While AI makes hypothesis generation effortless, the path to a concrete, executable plan remains a significant bottleneck. In a competitive research environment, this tool provides a decisive advantage by automating the logistical groundwork, allowing me to focus more on innovation and benchwork rather than administrative planning."*
> — PI, Biotech

---

<div align="center">
<sub>Built for researchers who want science at the speed of thought, without giving up the receipts.</sub>
</div>
