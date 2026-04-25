from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.services.corpus_retriever import corpus_manifest
from app.services.feedback_memory_index import index_feedback_memories
from app.services.hypothesis import structure_hypothesis
from app.services.observability import flush_observability, observability_status
from app.services.openalex import search_papers
from app.services.protocol_db import (
    create_feedback_memories_for_session,
    create_protocol_feedback,
    create_protocol_session,
    get_latest_protocol_version,
    list_transparency_events,
    get_protocol_session_detail,
    get_protocol_session_record,
    get_protocol_version,
    init_protocol_tables,
    mark_protocol_session_accepted,
    stop_protocol_session,
)
from app.services.protocol_models import (
    ProtocolAcceptRequest,
    ProtocolFeedbackCreate,
    ProtocolReviseRequest,
    ProtocolSessionCreate,
)
from app.services.protocol_orchestrator import (
    generate_initial_protocol_version,
    revise_protocol_version,
)
from app.services.protocols_io import search_protocols
from app.services.qc import run_literature_qc
from app.services.protocol_ranking import rank_protocols
from app.services.query_expansion import (
    build_query_debug,
    generate_paper_search_queries,
    generate_protocol_search_queries,
    normalize_scientific_query,
)
from app.services.ranking import rank_results

load_dotenv()
init_protocol_tables()

app = FastAPI(title="AI Scientist Lite", version="0.1.0")
MAX_PROTOCOL_VERSIONS = 3

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LiteratureQCRequest(BaseModel):
    query: str = Field(..., min_length=3)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/protocol-corpus/stats")
def protocol_corpus_stats() -> dict:
    return corpus_manifest()


@app.get("/api/observability/status")
def observability_status_endpoint() -> dict:
    return observability_status()


@app.on_event("shutdown")
def shutdown_observability() -> None:
    flush_observability()


@app.post("/api/literature-qc")
def literature_qc(payload: LiteratureQCRequest) -> dict:
    query = payload.query.strip()
    normalized_query = normalize_scientific_query(query)
    structured_hypothesis = structure_hypothesis(normalized_query)
    paper_search_queries = generate_paper_search_queries(normalized_query, structured_hypothesis)
    protocol_search_queries = generate_protocol_search_queries(normalized_query, structured_hypothesis)
    debug = build_query_debug(normalized_query, structured_hypothesis)
    warnings: list[str] = []

    try:
        raw_papers = search_papers(paper_search_queries, limit=8)
    except Exception:
        raw_papers = []
        warnings.append("OpenAlex search failed; no papers were returned.")

    try:
        raw_protocols = search_protocols(protocol_search_queries, limit=16)
    except Exception:
        raw_protocols = []
        warnings.append("Protocol search failed; no protocols were returned.")

    papers = rank_results(raw_papers, structured_hypothesis, limit=5)
    protocols = rank_protocols(
        raw_protocols,
        structured_hypothesis,
        protocol_search_queries,
        limit=10,
    )
    qc = run_literature_qc(structured_hypothesis, papers, protocols)

    return {
        "query": query,
        "structured_hypothesis": structured_hypothesis,
        "qc": qc,
        "papers": papers,
        "protocols": protocols,
        "warnings": warnings,
        "debug": debug,
    }


@app.post("/api/protocol-sessions")
def create_protocol_session_endpoint(payload: ProtocolSessionCreate) -> dict[str, str]:
    if not payload.selected_protocols:
        raise HTTPException(
            status_code=400,
            detail="Select at least one protocol before creating a protocol session.",
        )
    session_id = create_protocol_session(payload)
    return {"session_id": session_id}


@app.get("/api/protocol-sessions/{session_id}")
def get_protocol_session_endpoint(session_id: str) -> dict:
    detail = get_protocol_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Protocol session not found.")
    return detail.model_dump()


@app.get("/api/protocol-sessions/{session_id}/events")
def get_protocol_session_events_endpoint(session_id: str) -> dict:
    session = get_protocol_session_record(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Protocol session not found.")
    events = list_transparency_events(session_id)
    return {"session_id": session_id, "events": [event.model_dump() for event in events]}


@app.post("/api/protocol-sessions/{session_id}/generate")
async def generate_protocol_endpoint(session_id: str) -> dict:
    result = await generate_initial_protocol_version(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Protocol session not found.")
    return {
        "session_id": session_id,
        "version": result.version.model_dump(),
        "prior_feedback_used": [memory.model_dump() for memory in result.prior_feedback_used],
        "reference_examples_used": [example.model_dump() for example in result.reference_examples_used],
        "verifier_report": result.verifier_report.model_dump(),
        "validation_report": result.validation_report.model_dump(),
    }


@app.post("/api/protocol-sessions/{session_id}/feedback")
def create_protocol_feedback_endpoint(session_id: str, payload: ProtocolFeedbackCreate) -> dict:
    session = get_protocol_session_record(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Protocol session not found.")

    version = get_protocol_version(payload.version_id)
    if not version or version.session_id != session_id:
        raise HTTPException(status_code=404, detail="Protocol version not found for this session.")

    feedback = create_protocol_feedback(session_id, payload)
    return feedback.model_dump()


@app.post("/api/protocol-sessions/{session_id}/revise")
async def revise_protocol_endpoint(session_id: str, payload: ProtocolReviseRequest | None = None) -> dict:
    previous_version = (
        get_protocol_version(payload.version_id)
        if payload and payload.version_id
        else get_latest_protocol_version(session_id)
    )
    if not previous_version or previous_version.session_id != session_id:
        raise HTTPException(status_code=404, detail="Protocol version not found for this session.")
    if previous_version.version_number >= MAX_PROTOCOL_VERSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Revision loop limit reached. Summarize the current validation findings "
                "for the researcher instead of generating another version."
            ),
        )
    result = await revise_protocol_version(
        session_id,
        previous_version.id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Protocol version not found for this session.")
    return {
        "session_id": session_id,
        "version": result.version.model_dump(),
        "prior_feedback_used": [memory.model_dump() for memory in result.prior_feedback_used],
        "reference_examples_used": [example.model_dump() for example in result.reference_examples_used],
        "verifier_report": result.verifier_report.model_dump(),
        "validation_report": result.validation_report.model_dump(),
    }


@app.post("/api/protocol-sessions/{session_id}/accept")
def accept_protocol_endpoint(session_id: str, payload: ProtocolAcceptRequest | None = None) -> dict:
    session = get_protocol_session_record(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Protocol session not found.")

    version = (
        get_protocol_version(payload.version_id)
        if payload and payload.version_id
        else get_latest_protocol_version(session_id)
    )
    if not version or version.session_id != session_id:
        raise HTTPException(status_code=404, detail="Protocol version not found for this session.")

    mark_protocol_session_accepted(session_id, version.id)
    memories = create_feedback_memories_for_session(session_id)
    indexed_count = index_feedback_memories(memories)
    detail = get_protocol_session_detail(session_id)
    return {
        "session": detail.model_dump() if detail else None,
        "accepted_version_id": version.id,
        "memories_saved": [memory.model_dump() for memory in memories],
        "memories_indexed": indexed_count,
    }


@app.post("/api/protocol-sessions/{session_id}/stop")
def stop_protocol_endpoint(session_id: str) -> dict:
    session = get_protocol_session_record(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Protocol session not found.")
    stop_protocol_session(session_id)
    detail = get_protocol_session_detail(session_id)
    return {"session": detail.model_dump() if detail else None}
