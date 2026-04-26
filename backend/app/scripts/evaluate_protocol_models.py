from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.services.corpus_retriever import retrieve_corpus_examples
from app.services.entity_validator import validate_entities
from app.services.evidence_extractor import extract_protocol_evidence
from app.services.feedback_memory_index import retrieve_feedback_memories
from app.services.hypothesis import structure_hypothesis
from app.services.protocol_generation import (
    generate_protocol_draft,
    protocol_generation_backend,
    protocol_generation_model,
    protocol_reasoning_effort,
)
from app.services.protocol_ranking import rank_protocols
from app.services.protocol_validator import validate_protocol_draft
from app.services.protocol_verifier import verify_protocol_draft
from app.services.protocols_io import search_protocols
from app.services.query_expansion import (
    build_query_debug,
    generate_protocol_search_queries,
    normalize_scientific_query,
)
from app.services.safety_classifier import classify_protocol_safety

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EVAL_DIR = DATA_DIR / "evaluations"

ASSEMBLOID_QUERY = (
    "Human cortical and striatal organoids derived from hiPSCs can be fused into an assembloid "
    "model to manifest functional inter-regional connectivity, allowing for the real-time "
    "interrogation of human-specific neurodevelopmental circuit assembly and the modeling of "
    "neuropsychiatric migration defects without animal-model surrogates"
)

TARGET_PROTOCOL_URL = (
    "https://www.protocols.io/view/engineering-brain-assembloids-to-interrogate-human-36wgq4xxkvk5/v1"
)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _target_protocol_rank(protocols: list[dict[str, Any]]) -> int | None:
    for index, protocol in enumerate(protocols, start=1):
        if protocol.get("url") == TARGET_PROTOCOL_URL or "36wgq4xxkvk5" in str(protocol.get("id") or ""):
            return index
    return None


def _protocol_source_ids(protocol: Any) -> list[str]:
    source_ids: list[str] = []
    for section_name in (
        "scientific_rationale",
        "materials_and_reagents",
        "adapted_workflow",
        "controls",
        "validation_readout",
        "risks_and_limitations",
    ):
        section = getattr(protocol, section_name, None)
        source_ids.extend(getattr(section, "source_ids", []) or [])
    return source_ids


def _build_case(query: str) -> dict[str, Any]:
    normalized_query = normalize_scientific_query(query)
    structured_hypothesis = structure_hypothesis(normalized_query)
    protocol_search_queries = generate_protocol_search_queries(normalized_query, structured_hypothesis)
    raw_protocols = search_protocols(protocol_search_queries, limit=16)
    ranked_protocols = rank_protocols(
        raw_protocols,
        structured_hypothesis,
        protocol_search_queries,
        limit=10,
    )
    target_rank = _target_protocol_rank(ranked_protocols)
    selected_protocol = (
        ranked_protocols[target_rank - 1]
        if target_rank is not None
        else ranked_protocols[0]
        if ranked_protocols
        else None
    )
    if not selected_protocol:
        raise RuntimeError("No protocol candidates were available for evaluation.")
    return {
        "query": query,
        "normalized_query": normalized_query,
        "structured_hypothesis": structured_hypothesis,
        "protocol_search_queries": protocol_search_queries,
        "query_debug": build_query_debug(normalized_query, structured_hypothesis),
        "ranked_protocols": ranked_protocols,
        "target_protocol_rank": target_rank,
        "selected_protocol": selected_protocol,
    }


def _evaluate_one(case: dict[str, Any], model: str, reasoning_effort: str) -> dict[str, Any]:
    os.environ["OPENAI_PROTOCOL_MODEL"] = model
    os.environ["OPENAI_PROTOCOL_REASONING_EFFORT"] = reasoning_effort

    session = {
        "id": f"eval:{model}:{reasoning_effort}",
        "original_query": case["query"],
        "structured_hypothesis": case["structured_hypothesis"],
        "selected_protocols": [case["selected_protocol"]],
        "selected_papers": [],
        "lab_context": None,
    }

    start = time.perf_counter()
    evidence = extract_protocol_evidence(session["selected_protocols"])
    memories = retrieve_feedback_memories(case["structured_hypothesis"], limit=5)
    examples = retrieve_corpus_examples(case["structured_hypothesis"], limit=5)
    safety = classify_protocol_safety(
        session["original_query"],
        session["structured_hypothesis"],
        session["selected_protocols"],
        session["lab_context"],
    )
    entities = validate_entities(case["structured_hypothesis"])
    draft = generate_protocol_draft(
        session,
        memories,
        examples,
        evidence,
        safety,
        entities,
    )
    verifier_report = verify_protocol_draft(draft, evidence)
    validation_report = validate_protocol_draft(
        protocol=draft,
        original_query=session["original_query"],
        structured_hypothesis=case["structured_hypothesis"],
        selected_protocols=session["selected_protocols"],
        protocol_evidence=evidence,
        prior_memories=memories,
    )
    elapsed_seconds = round(time.perf_counter() - start, 3)
    section_source_ids = _protocol_source_ids(draft)

    return {
        "model": draft.generation_model or protocol_generation_model(),
        "reasoning_effort": draft.reasoning_effort or protocol_reasoning_effort(),
        "generation_backend": draft.generation_backend or protocol_generation_backend(),
        "generation_error": draft.generation_error,
        "elapsed_seconds": elapsed_seconds,
        "selected_protocol_title": case["selected_protocol"].get("title"),
        "target_protocol_rank": case["target_protocol_rank"],
        "protocol_title": draft.title,
        "experiment_type": draft.experiment_type,
        "verifier_passed": verifier_report.passed,
        "validation_status": validation_report.overall_status,
        "grounding_score": validation_report.grounding_score,
        "completeness_score": validation_report.completeness_score,
        "safety_status": validation_report.safety_status,
        "issue_count": len(validation_report.issues),
        "missing_information_count": len(validation_report.missing_information),
        "prior_memory_count": len(memories),
        "corpus_example_count": len(examples),
        "evidence_steps_count": sum(len(item.steps) for item in evidence),
        "evidence_materials_count": sum(len(item.materials) for item in evidence),
        "major_section_source_id_count": len(section_source_ids),
        "unique_major_section_source_id_count": len(set(section_source_ids)),
        "open_question_count": len(draft.open_questions),
        "validation_report": validation_report.model_dump(),
        "verifier_report": verifier_report.model_dump(),
    }


def _write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = EVAL_DIR / f"protocol_model_eval_{stamp}.json"
    csv_path = EVAL_DIR / f"protocol_model_eval_{stamp}.csv"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    rows = payload["results"]
    scalar_keys = [
        "model",
        "reasoning_effort",
        "generation_backend",
        "elapsed_seconds",
        "target_protocol_rank",
        "validation_status",
        "grounding_score",
        "completeness_score",
        "safety_status",
        "issue_count",
        "missing_information_count",
        "prior_memory_count",
        "corpus_example_count",
        "evidence_steps_count",
        "evidence_materials_count",
        "major_section_source_id_count",
        "open_question_count",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=scalar_keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in scalar_keys})
    return json_path, csv_path


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Evaluate protocol-generation models on a fixed assembloid case.")
    parser.add_argument("--query", default=ASSEMBLOID_QUERY, help="Researcher prompt to evaluate.")
    parser.add_argument(
        "--models",
        default="gpt-5.2,gpt-5.1,gpt-5-mini",
        help="Comma-separated OpenAI model IDs to evaluate.",
    )
    parser.add_argument(
        "--reasoning-efforts",
        default="low,medium,high",
        help="Comma-separated reasoning_effort values.",
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Only validate retrieval/ranking and skip protocol generation.",
    )
    args = parser.parse_args()

    case = _build_case(args.query)
    results: list[dict[str, Any]] = []
    if not args.retrieval_only:
        for model in _split_csv(args.models):
            for effort in _split_csv(args.reasoning_efforts):
                results.append(_evaluate_one(case, model, effort))

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "query": case["query"],
        "structured_hypothesis": case["structured_hypothesis"],
        "protocol_search_queries": case["protocol_search_queries"],
        "semantic_weight_profile": case["query_debug"].get("semantic_weight_profile"),
        "target_protocol_url": TARGET_PROTOCOL_URL,
        "target_protocol_rank": case["target_protocol_rank"],
        "selected_protocol": case["selected_protocol"],
        "ranked_protocols": [
            {
                "rank": index,
                "title": protocol.get("title"),
                "url": protocol.get("url"),
                "match_score": protocol.get("match_score"),
                "match_tier": protocol.get("match_tier"),
                "match_reason": protocol.get("match_reason"),
            }
            for index, protocol in enumerate(case["ranked_protocols"], start=1)
        ],
        "results": results,
    }
    json_path, csv_path = _write_outputs(payload)
    print(
        json.dumps(
            {
                "json_path": str(json_path),
                "csv_path": str(csv_path),
                "target_protocol_rank": case["target_protocol_rank"],
                "selected_protocol_title": case["selected_protocol"].get("title"),
                "results": [
                    {
                        "model": row.get("model"),
                        "reasoning_effort": row.get("reasoning_effort"),
                        "backend": row.get("generation_backend"),
                        "status": row.get("validation_status"),
                        "grounding_score": row.get("grounding_score"),
                        "completeness_score": row.get("completeness_score"),
                        "elapsed_seconds": row.get("elapsed_seconds"),
                    }
                    for row in results
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
