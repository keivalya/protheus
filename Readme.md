Build the hackathon app in narrow milestones.

Project name: AI Scientist Lite

Current goal:
Build a working app that takes a scientific hypothesis from the user, structures it, searches for related scientific papers and protocols, returns a Literature QC result, then lets the researcher generate and review a structured custom protocol draft from selected evidence.

Current milestone:
Custom Protocol Generation + Researcher Feedback Loop + Feedback Memory.

Do NOT build experiment planning yet.
Do NOT build budget, timeline, material sourcing, or lab profile yet.
Do NOT build budget, timeline, supplier sourcing, or final executable lab SOPs.

Current flow:
User Query -> Hypothesis Structuring -> Paper Search -> Protocol Search -> Literature QC -> Selected Evidence -> Researcher-Review Protocol Draft -> Section Feedback -> Revised Versions -> Accepted Feedback Memory

Custom Protocol Module architecture:

```text
Selected protocols
+ lab context
+ prior feedback memory
+ retrieved corpus examples
+ optional papers
  ↓
Protocol orchestrator
  ↓
Parallel helper modules:
  - evidence extractor
  - feedback memory retriever
  - corpus example retriever
  - safety classifier
  - entity validator
  ↓
Custom protocol generator
  ↓
Validation agent
  ↓
Protocol draft + validation report
  ↓
Researcher feedback
  ↓
Revision loop, max 2 revisions
  ↓
Accept or stop
```

Source hierarchy:

```text
1. Selected protocols = primary evidence
2. Lab context = constraints
3. Feedback memory = prior accepted researcher corrections
4. Corpus examples = structural guidance only
5. Papers = optional background/rationale only
6. Safety rules = override everything
```

Retrieval policy:

```text
BM25 + metadata + RapidFuzz first.
Embeddings/ChromaDB are optional search indexes for feedback memory and corpus examples only.
Do not use embeddings for safety decisions, source grounding, final validation, or selected-protocol relevance.
SQLite is the source of truth.
Curated corpus JSON is the source of truth for grounding examples; ChromaDB can be rebuilt.
```

Local corpus:

```text
Runtime:
- protocols.io selected protocols
- user feedback memory
- curated 5,000-example BioProBench/BioProt/Wet Lab Protocol Corpus subset
- optional OpenAlex papers

Validation/schema guidance:
- Wet Lab Protocol Corpus
- LabOP / Autoprotocol concepts

Later validation:
- Cellosaurus
- PubChem / ChEBI
```

Corpus commands:

```bash
cd backend
.venv/bin/python app/scripts/download_grounding_datasets.py
.venv/bin/python app/scripts/index_corpus_embeddings.py --batch-size 128
```

Free local observability:

```text
LOCAL_PROTOCOL_TRACING_ENABLED=true
```

Local JSONL traces record the custom protocol pipeline for clarity: context preparation, retrieval counts, generator stage, verifier, validation agent, revision, version number and validation scores. They do not decide grounding, safety or acceptance.

Custom protocol transparency:

```text
GET /api/protocol-sessions/{session_id}/events
```

The frontend polls this endpoint while a protocol draft or revision is running. Events are stored in SQLite and shown as a compact researcher-facing timeline: selected-protocol reading, evidence extraction, corpus retrieval, feedback memory retrieval, safety check, drafting, validation and ready-for-review.

The challenge requires a natural-language scientific question and a Literature QC step that checks whether the experiment, or something very close to it, has been done before. The QC output should return one of:
- exact match found
- similar work exists
- not found

Core APIs:
- Papers: OpenAlex
- Protocols: protocols.io
- If protocols.io token is missing, use mock protocol data so the demo still works.

Tech stack:
- Frontend: React + Vite + TypeScript
- Backend: FastAPI + Python
- Database: SQLite source of truth; ChromaDB optional embedding index
- Observability: free local JSONL protocol traces
- Styling: Tailwind CSS

Frontend requirements:
Create one clean page with:
1. A text box where the user enters a scientific hypothesis
2. A “Run Literature QC” button
3. Loading states:
   - Structuring hypothesis
   - Searching papers
   - Searching protocols
   - Running literature QC
4. A structured hypothesis card showing:
   - domain
   - model system
   - intervention
   - control
   - outcome
   - effect size
   - assay
   - mechanism
   - keywords
5. A Literature QC card showing:
   - novelty signal: exact match found / similar work exists / not found
   - confidence score
   - explanation
6. A Papers section showing top 5 papers
7. A Protocols section showing top 10 protocols
8. Each paper/protocol card should show:
   - title
   - source
   - year if available
   - URL if available
   - match score
   - match reason
9. Add checkboxes only for protocols. Papers are shown as read-only background context and are not selectable.

Backend requirements:
Create one main API endpoint:

POST /api/literature-qc

Request:
{
  "query": "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol."
}

Response:
{
  "query": "...",
  "structured_hypothesis": {
    "domain": "...",
    "model_system": "...",
    "intervention": "...",
    "control": "...",
    "outcome": "...",
    "effect_size": "...",
    "assay": "...",
    "mechanism": "...",
    "keywords": ["..."]
  },
  "qc": {
    "novelty_signal": "similar work exists",
    "confidence": 0.76,
    "explanation": "Related work exists, but no exact match was found for this precise model, intervention, control and outcome."
  },
  "papers": [],
  "protocols": []
}

Backend modules:
backend/
  app/
    main.py
    services/
      hypothesis.py
      openalex.py
      protocols_io.py
      ranking.py
      qc.py
    data/
      mock_protocols.json
  requirements.txt
  .env.example

Frontend modules:
frontend/
  src/
    App.tsx
    api.ts
    types.ts
    components/
      QueryInput.tsx
      StructuredHypothesisCard.tsx
      QCSignalCard.tsx
      PaperResults.tsx
      ProtocolResults.tsx
  package.json

Implementation details:

1. Hypothesis structuring
Create a function:

structure_hypothesis(query: str) -> dict

For now, use simple rule-based extraction or an LLM if OPENAI_API_KEY is available.
Do not hallucinate. Unknown values should be null.

Return:
- domain
- model_system
- intervention
- control
- outcome
- effect_size
- assay
- mechanism
- keywords

2. Search query generation
Generate 3 search queries from the structured hypothesis:
- exact-style query
- broader method query
- protocol-style query

Example:
[
  "HeLa trehalose cryopreservation post-thaw viability DMSO",
  "trehalose cryoprotectant HeLa cells freezing protocol",
  "post-thaw viability trehalose DMSO cell cryopreservation"
]

3. Paper search
Create OpenAlex search wrapper.

Function:
search_papers(search_queries: list[str], limit: int = 5) -> list[dict]

For each paper return:
- id
- title
- year
- doi
- url
- authors
- abstract if available
- citation_count
- source = "OpenAlex"

Deduplicate papers by DOI or normalized title.

4. Protocol search
Create protocols.io wrapper.

Function:
search_protocols(search_queries: list[str], limit: int = 10) -> list[dict]

If PROTOCOLS_IO_TOKEN exists, call protocols.io.
If not, load results from mock_protocols.json.

For each protocol return:
- id
- title
- url
- source = "protocols.io"
- description
- steps_preview
- materials_preview

5. Ranking
Create ranking.py.

Score each paper and protocol based on keyword overlap:
- intervention match
- model system match
- outcome match
- control match
- assay/method match

Return:
- match_score between 0 and 1
- match_reason as one sentence

Keep the scoring simple and explainable.

6. Literature QC
Create qc.py.

Rules:
- exact match found: one result strongly matches model system, intervention, control and outcome
- similar work exists: one or more results match part of the hypothesis
- not found: no meaningful matches found

Use conservative wording.
Never say “this has never been done.”
Say “No close match was found in the searched sources.”

7. Error handling
The app should not crash if one API fails.
If OpenAlex fails, return empty papers with a warning.
If protocols.io fails or token is missing, use mock protocol data.

8. Seed examples
Add these clickable examples in the frontend:

Example 1:
Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol.

Example 2:
A paper-based electrochemical biosensor functionalized with anti-CRP antibodies will detect C-reactive protein in whole blood below 0.5 mg/L within 10 minutes.

Example 3:
Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG for 4 weeks will reduce intestinal permeability by at least 30 percent compared to controls.

Acceptance criteria:
- I can enter a scientific hypothesis
- The backend structures the hypothesis
- The backend searches papers
- The backend searches protocols or uses mock protocols
- The backend ranks results
- The backend returns exact match found / similar work exists / not found
- The frontend displays top 5 papers
- The frontend displays top 10 protocols
- The frontend displays a Literature QC result with confidence and explanation
- The app does not build the custom protocol yet
- The app does not build the experiment plan yet
