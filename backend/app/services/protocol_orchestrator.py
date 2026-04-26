from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.services.corpus_retriever import retrieve_corpus_examples
from app.services.entity_validator import validate_entities
from app.services.evidence_extractor import extract_protocol_evidence
from app.services.feedback_memory_index import retrieve_feedback_memories
from app.services.observability import trace_span
from app.services.protocol_db import (
    create_protocol_version,
    emit_transparency_event,
    get_latest_protocol_version,
    get_protocol_session_record,
    list_protocol_feedback,
)
from app.services.protocol_generation import (
    generate_protocol_draft,
    protocol_agent_context_summary,
    protocol_generation_backend,
    protocol_generation_model,
    protocol_reasoning_effort,
    revise_protocol_draft,
)
from app.services.protocol_models import (
    FeedbackMemoryReference,
    CorpusExampleReference,
    ProtocolValidationReport,
    ProtocolVerifierReport,
    ProtocolVersionResponse,
)
from app.services.protocol_validator import validate_protocol_draft
from app.services.protocol_verifier import verify_protocol_draft
from app.services.safety_classifier import classify_protocol_safety


@dataclass
class ProtocolOrchestrationResult:
    version: ProtocolVersionResponse
    prior_feedback_used: list[FeedbackMemoryReference]
    reference_examples_used: list[CorpusExampleReference]
    verifier_report: ProtocolVerifierReport
    validation_report: ProtocolValidationReport


def _session_trace_input(session: dict) -> dict:
    return {
        "query_preview": str(session.get("original_query") or "")[:240],
        "structured_hypothesis": session.get("structured_hypothesis") or {},
        "selected_protocol_count": len(session.get("selected_protocols") or []),
        "selected_paper_count": len(session.get("selected_papers") or []),
        "has_lab_context": bool(session.get("lab_context")),
    }


def _risk_level(value: object) -> str | None:
    return getattr(value, "risk_level", None)


def _safety_flags(value: object) -> list[str]:
    return list(getattr(value, "flags", []) or [])


def _requires_expert_review(value: object) -> bool:
    return bool(getattr(value, "requires_expert_review", False))


def _evidence_counts(evidence: list) -> dict:
    missing_fields = sorted(
        {
            missing
            for item in evidence
            for missing in getattr(item, "missing_fields", []) or []
        }
    )
    return {
        "protocols_read": len(evidence),
        "steps_extracted": sum(len(getattr(item, "steps", []) or []) for item in evidence),
        "materials_extracted": sum(len(getattr(item, "materials", []) or []) for item in evidence),
        "equipment_items": sum(len(getattr(item, "equipment", []) or []) for item in evidence),
        "validation_methods": sum(len(getattr(item, "validation_methods", []) or []) for item in evidence),
        "missing_fields": missing_fields,
    }


def _context_counts(evidence, memories, examples, safety, entities) -> dict:
    context = protocol_agent_context_summary(
        protocol_evidence=evidence,
        prior_memories=memories,
        reference_examples=examples,
        safety_review=safety,
        validated_entities=entities,
    )
    return {
        "model": protocol_generation_model(),
        "reasoning_effort": protocol_reasoning_effort(),
        "generation_backend": protocol_generation_backend(),
        "selected_evidence": context["selected_evidence"],
        "prior_feedback": {
            "accepted_feedback_memories": context["prior_feedback"]["accepted_feedback_memories"],
            "sections": context["prior_feedback"]["sections"],
        },
        "structure_references": {
            "structure_examples_retrieved": context["structure_references"]["structure_examples_retrieved"],
            "allowed_use": context["structure_references"]["allowed_use"],
        },
        "safety_review": {
            "risk_level": context["safety_review"].get("risk_level"),
            "requires_expert_review": context["safety_review"].get("requires_expert_review"),
        },
        "entity_normalization": {"validated_entity_count": len(entities)},
    }


def _emit_event(
    session_id: str,
    stage: str,
    status: str,
    user_message: str,
    details: dict | None = None,
    version_id: str | None = None,
) -> None:
    emit_transparency_event(
        session_id=session_id,
        stage=stage,
        status=status,  # type: ignore[arg-type]
        user_message=user_message,
        details=details or {},
        version_id=version_id,
    )


async def _prepare_context(session: dict) -> tuple:
    structured_hypothesis = session.get("structured_hypothesis") or {}
    selected_protocols = session.get("selected_protocols") or []
    lab_context = session.get("lab_context")
    session_id = session.get("id") or ""

    _emit_event(
        session_id,
        "reading_selected_protocols",
        "running",
        "Reading selected protocols.",
        {"selected_protocol_count": len(selected_protocols)},
    )
    _emit_event(
        session_id,
        "evidence_extraction",
        "running",
        "Extracting selected protocol evidence.",
    )
    _emit_event(
        session_id,
        "corpus_example_retrieval",
        "running",
        "Checking structure references.",
    )
    _emit_event(
        session_id,
        "feedback_memory_retrieval",
        "running",
        "Checking reusable feedback.",
    )
    _emit_event(
        session_id,
        "safety_check",
        "running",
        "Running safety review.",
    )

    with trace_span(
        "protocol.prepare_context",
        input_data=_session_trace_input(session),
        metadata={"stage": "context_preparation"},
        session_id=session.get("id"),
        tags=["custom_protocol", "context"],
    ) as span:
        evidence, memories, examples, safety, entities = await asyncio.gather(
            asyncio.to_thread(extract_protocol_evidence, selected_protocols),
            asyncio.to_thread(retrieve_feedback_memories, structured_hypothesis, 5),
            asyncio.to_thread(retrieve_corpus_examples, structured_hypothesis, 5),
            asyncio.to_thread(
                classify_protocol_safety,
                session.get("original_query") or "",
                structured_hypothesis,
                selected_protocols,
                lab_context,
            ),
            asyncio.to_thread(validate_entities, structured_hypothesis),
        )
        span.update(
            output={
                "evidence_count": len(evidence),
                "prior_memory_count": len(memories),
                "corpus_example_count": len(examples),
                "corpus_search_backends": sorted({example.search_backend for example in examples}),
                "safety_risk_level": _risk_level(safety),
                "entity_count": len(entities),
            }
        )
    evidence_counts = _evidence_counts(evidence)
    _emit_event(
        session_id,
        "reading_selected_protocols",
        "completed",
        f"Read {len(selected_protocols)} selected protocol{'' if len(selected_protocols) == 1 else 's'}.",
        {"selected_protocol_count": len(selected_protocols)},
    )
    _emit_event(
        session_id,
        "evidence_extraction",
        "completed",
        "Evidence extraction complete.",
        evidence_counts,
    )
    _emit_event(
        session_id,
        "corpus_example_retrieval",
        "completed",
        "Structure references checked.",
        {
            "example_count": len(examples),
            "search_backends": sorted({example.search_backend for example in examples}),
            "sources": sorted({example.source for example in examples}),
        },
    )
    _emit_event(
        session_id,
        "feedback_memory_retrieval",
        "completed",
        "Reusable feedback checked.",
        {
            "memory_count": len(memories),
            "sections": sorted({memory.section for memory in memories if memory.section}),
            "search_backends": sorted({memory.search_backend for memory in memories}),
        },
    )
    safety_status = "completed" if _risk_level(safety) == "low_risk" else "warning"
    _emit_event(
        session_id,
        "safety_check",
        safety_status,
        "Safety review complete.",
        {
            "risk_level": _risk_level(safety),
            "flags": _safety_flags(safety),
            "requires_expert_review": _requires_expert_review(safety),
        },
    )
    return evidence, memories, examples, safety, entities


async def generate_initial_protocol_version(session_id: str) -> ProtocolOrchestrationResult | None:
    session = get_protocol_session_record(session_id)
    if not session:
        return None

    with trace_span(
        "custom_protocol.generate",
        input_data=_session_trace_input(session),
        metadata={"stage": "initial_generation"},
        session_id=session_id,
        trace_name="custom-protocol-generation",
        tags=["custom_protocol", "generate"],
    ) as root_span:
        evidence, memories, examples, safety, entities = await _prepare_context(session)
        _emit_event(
            session_id,
            "protocol_drafting",
            "running",
            "Composing protocol draft.",
            {
                **_context_counts(evidence, memories, examples, safety, entities),
                "evidence_count": len(evidence),
                "prior_memory_count": len(memories),
                "corpus_example_count": len(examples),
            },
        )
        with trace_span(
            "custom_protocol.generator",
            as_type="generation",
            input_data={
                "model": protocol_generation_model(),
                "reasoning_effort": protocol_reasoning_effort(),
                "generation_backend": protocol_generation_backend(),
                "evidence_count": len(evidence),
                "prior_memory_count": len(memories),
                "corpus_example_count": len(examples),
                "safety_risk_level": _risk_level(safety),
            },
            metadata={"stage": "draft_generation"},
            session_id=session_id,
            tags=["custom_protocol", "generator"],
        ) as generator_span:
            protocol = await asyncio.to_thread(
                generate_protocol_draft,
                session,
                memories,
                examples,
                evidence,
                safety,
                entities,
            )
            generator_span.update(
                output={
                    "title": protocol.title,
                    "experiment_type": protocol.experiment_type,
                    "generation_backend": protocol.generation_backend,
                    "generation_error": protocol.generation_error,
                    "source_evidence_count": len(protocol.source_evidence_used),
                    "reference_examples_used": len(protocol.reference_examples_used),
                }
            )
        _emit_event(
            session_id,
            "protocol_drafting",
            "completed",
            "Protocol draft composed.",
            {
                "model": protocol.generation_model or protocol_generation_model(),
                "reasoning_effort": protocol.reasoning_effort or protocol_reasoning_effort(),
                "generation_backend": protocol.generation_backend or protocol_generation_backend(),
                "generation_error": protocol.generation_error,
                "title": protocol.title,
                "source_evidence_count": len(protocol.source_evidence_used),
                "reference_examples_used": len(protocol.reference_examples_used),
                "prior_feedback_used": len(protocol.prior_feedback_used),
            },
        )
        _emit_event(
            session_id,
            "protocol_validation",
            "running",
            "Validating draft.",
        )
        with trace_span(
            "custom_protocol.verifier",
            input_data={"source_evidence_count": len(protocol.source_evidence_used)},
            metadata={"stage": "grounding_verification"},
            session_id=session_id,
            tags=["custom_protocol", "verifier"],
        ) as verifier_span:
            verifier_report = verify_protocol_draft(protocol, evidence)
            verifier_span.update(output=verifier_report.model_dump())
        with trace_span(
            "custom_protocol.validator",
            input_data={"title": protocol.title},
            metadata={"stage": "validation_review"},
            session_id=session_id,
            tags=["custom_protocol", "validator"],
        ) as validator_span:
            validation_report = validate_protocol_draft(
                protocol=protocol,
                original_query=session.get("original_query") or "",
                structured_hypothesis=session.get("structured_hypothesis") or {},
                selected_protocols=session.get("selected_protocols") or [],
                protocol_evidence=evidence,
                prior_memories=memories,
            )
            validator_span.update(
                output={
                    "overall_status": validation_report.overall_status,
                    "grounding_score": validation_report.grounding_score,
                    "completeness_score": validation_report.completeness_score,
                    "safety_status": validation_report.safety_status,
                    "issue_count": len(validation_report.issues),
                    "missing_information_count": len(validation_report.missing_information),
                }
            )
        version = create_protocol_version(
            session_id=session_id,
            protocol=protocol,
            verifier_report=verifier_report,
            validation_report=validation_report,
            change_summary="Generated initial researcher-review protocol draft.",
        )
        validation_status = (
            "completed"
            if validation_report.overall_status == "pass"
            else "failed"
            if validation_report.overall_status == "blocked"
            else "warning"
        )
        _emit_event(
            session_id,
            "protocol_validation",
            validation_status,
            "Validation review complete.",
            {
                "overall_status": validation_report.overall_status,
                "grounding_score": validation_report.grounding_score,
                "completeness_score": validation_report.completeness_score,
                "safety_status": validation_report.safety_status,
                "issue_count": len(validation_report.issues),
                "missing_information_count": len(validation_report.missing_information),
                "verifier_passed": verifier_report.passed,
            },
            version_id=version.id,
        )
        _emit_event(
            session_id,
            "ready_for_review",
            "completed",
            f"Protocol v{version.version_number} ready.",
            {
                "version_id": version.id,
                "version_number": version.version_number,
                "validation_status": validation_report.overall_status,
                "safety_status": validation_report.safety_status,
            },
            version_id=version.id,
        )
        root_span.update(
            output={
                "version_id": version.id,
                "version_number": version.version_number,
                "validation_status": validation_report.overall_status,
                "grounding_score": validation_report.grounding_score,
                "completeness_score": validation_report.completeness_score,
            }
        )
    return ProtocolOrchestrationResult(version, memories, examples, verifier_report, validation_report)


async def revise_protocol_version(
    session_id: str,
    version_id: str | None = None,
) -> ProtocolOrchestrationResult | None:
    session = get_protocol_session_record(session_id)
    if not session:
        return None

    previous_version = get_latest_protocol_version(session_id)
    if version_id:
        from app.services.protocol_db import get_protocol_version

        previous_version = get_protocol_version(version_id)

    if not previous_version or previous_version.session_id != session_id:
        return None

    with trace_span(
        "custom_protocol.revise",
        input_data={
            **_session_trace_input(session),
            "previous_version_id": previous_version.id,
            "previous_version_number": previous_version.version_number,
        },
        metadata={"stage": "revision"},
        session_id=session_id,
        trace_name="custom-protocol-revision",
        tags=["custom_protocol", "revise"],
    ) as root_span:
        evidence, memories, examples, safety, entities = await _prepare_context(session)
        feedback = list_protocol_feedback(session_id, version_id=previous_version.id)
        _emit_event(
            session_id,
            "protocol_drafting",
            "running",
            f"Composing protocol v{previous_version.version_number + 1}.",
            {
                **_context_counts(evidence, memories, examples, safety, entities),
                "previous_version_id": previous_version.id,
                "previous_version_number": previous_version.version_number,
                "feedback_count": len(feedback),
                "prior_memory_count": len(memories),
                "corpus_example_count": len(examples),
            },
        )
        with trace_span(
            "custom_protocol.revision_generator",
            as_type="generation",
            input_data={
                "model": protocol_generation_model(),
                "reasoning_effort": protocol_reasoning_effort(),
                "generation_backend": protocol_generation_backend(),
                "previous_version_number": previous_version.version_number,
                "feedback_count": len(feedback),
                "prior_memory_count": len(memories),
                "corpus_example_count": len(examples),
                "safety_risk_level": _risk_level(safety),
            },
            metadata={"stage": "revision_generation"},
            session_id=session_id,
            tags=["custom_protocol", "generator"],
        ) as generator_span:
            protocol, change_summary = await asyncio.to_thread(
                revise_protocol_draft,
                session,
                memories,
                previous_version,
                feedback,
                examples,
                evidence,
                safety,
                entities,
            )
            generator_span.update(
                output={
                    "title": protocol.title,
                    "change_summary": change_summary,
                    "generation_backend": protocol.generation_backend,
                    "generation_error": protocol.generation_error,
                    "source_evidence_count": len(protocol.source_evidence_used),
                }
            )
        _emit_event(
            session_id,
            "protocol_drafting",
            "completed",
            "Protocol draft composed.",
            {
                "model": protocol.generation_model or protocol_generation_model(),
                "reasoning_effort": protocol.reasoning_effort or protocol_reasoning_effort(),
                "generation_backend": protocol.generation_backend or protocol_generation_backend(),
                "generation_error": protocol.generation_error,
                "title": protocol.title,
                "source_evidence_count": len(protocol.source_evidence_used),
                "feedback_count": len(feedback),
                "change_summary": change_summary,
            },
        )
        _emit_event(
            session_id,
            "protocol_validation",
            "running",
            "Validating draft.",
        )
        with trace_span(
            "custom_protocol.revision_verifier",
            input_data={"source_evidence_count": len(protocol.source_evidence_used)},
            metadata={"stage": "grounding_verification"},
            session_id=session_id,
            tags=["custom_protocol", "verifier"],
        ) as verifier_span:
            verifier_report = verify_protocol_draft(protocol, evidence)
            verifier_span.update(output=verifier_report.model_dump())
        with trace_span(
            "custom_protocol.revision_validator",
            input_data={"title": protocol.title},
            metadata={"stage": "validation_review"},
            session_id=session_id,
            tags=["custom_protocol", "validator"],
        ) as validator_span:
            validation_report = validate_protocol_draft(
                protocol=protocol,
                original_query=session.get("original_query") or "",
                structured_hypothesis=session.get("structured_hypothesis") or {},
                selected_protocols=session.get("selected_protocols") or [],
                protocol_evidence=evidence,
                prior_memories=memories,
            )
            validator_span.update(
                output={
                    "overall_status": validation_report.overall_status,
                    "grounding_score": validation_report.grounding_score,
                    "completeness_score": validation_report.completeness_score,
                    "safety_status": validation_report.safety_status,
                    "issue_count": len(validation_report.issues),
                    "missing_information_count": len(validation_report.missing_information),
                }
            )
        version = create_protocol_version(
            session_id=session_id,
            protocol=protocol,
            parent_version_id=previous_version.id,
            verifier_report=verifier_report,
            validation_report=validation_report,
            change_summary=change_summary,
        )
        validation_status = (
            "completed"
            if validation_report.overall_status == "pass"
            else "failed"
            if validation_report.overall_status == "blocked"
            else "warning"
        )
        _emit_event(
            session_id,
            "protocol_validation",
            validation_status,
            "Validation review complete.",
            {
                "overall_status": validation_report.overall_status,
                "grounding_score": validation_report.grounding_score,
                "completeness_score": validation_report.completeness_score,
                "safety_status": validation_report.safety_status,
                "issue_count": len(validation_report.issues),
                "missing_information_count": len(validation_report.missing_information),
                "verifier_passed": verifier_report.passed,
            },
            version_id=version.id,
        )
        _emit_event(
            session_id,
            "ready_for_review",
            "completed",
            f"Protocol v{version.version_number} ready.",
            {
                "version_id": version.id,
                "version_number": version.version_number,
                "validation_status": validation_report.overall_status,
                "safety_status": validation_report.safety_status,
            },
            version_id=version.id,
        )
        root_span.update(
            output={
                "version_id": version.id,
                "version_number": version.version_number,
                "validation_status": validation_report.overall_status,
                "grounding_score": validation_report.grounding_score,
                "completeness_score": validation_report.completeness_score,
            }
        )
    return ProtocolOrchestrationResult(version, memories, examples, verifier_report, validation_report)
