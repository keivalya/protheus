from __future__ import annotations

import json
import os
from typing import Any

from app.services.protocol_models import (
    CorpusExampleReference,
    CustomProtocolDraft,
    EntityValidation,
    ExtractedProtocolEvidence,
    FeedbackMemoryReference,
    MaterialItem,
    ProtocolFeedbackResponse,
    ProtocolSection,
    ProtocolVersionResponse,
    SafetyReview,
    WorkflowParameters,
    WorkflowPhase,
    WorkflowStep,
)

SECTION_KEYS = [
    "scientific_rationale",
    "materials_and_reagents",
    "adapted_workflow",
    "controls",
    "validation_readout",
    "risks_and_limitations",
]

DEFAULT_PROTOCOL_MODEL = "gpt-5.1"
DEFAULT_PROTOCOL_REASONING_EFFORT = "medium"
DEFAULT_PROTOCOL_MAX_COMPLETION_TOKENS = 12000
PROTOCOL_CONTEXT_ROLES = {
    "evidence_extraction_agent": (
        "Extracts protocol steps, materials, equipment, conditions, warnings, validation methods, "
        "and missing fields from the selected protocols."
    ),
    "prior_feedback_index": (
        "Retrieves accepted prior researcher corrections relevant to the current hypothesis. "
        "This is retrieval context, not a protocol-generating agent."
    ),
    "structure_reference_retriever": (
        "Retrieves similar local corpus examples for structure only. It cannot override selected protocols."
    ),
    "safety_review_agent": (
        "Classifies risk and can force expert review or redact operational details."
    ),
    "entity_normalizer": (
        "Normalizes scientific entities from the structured hypothesis."
    ),
    "protocol_composer_agent": (
        "Writes the structured researcher-review draft from the agent context bundle."
    ),
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_safe_text(item) for item in value)
    return str(value).strip()


def _evidence_id(prefix: str, item: dict[str, Any], index: int) -> str:
    raw_id = _safe_text(item.get("id") or item.get("doi") or item.get("url") or item.get("title"))
    return f"{prefix}:{raw_id or index}"


def build_evidence_pack(session: dict[str, Any]) -> dict[str, Any]:
    papers = session.get("selected_papers") or []
    protocols = session.get("selected_protocols") or []
    evidence_items: list[dict[str, Any]] = []

    for index, paper in enumerate(papers, start=1):
        evidence_items.append(
            {
                "source_id": _evidence_id("paper", paper, index),
                "kind": "paper",
                "title": paper.get("title"),
                "year": paper.get("year"),
                "url": paper.get("url"),
                "summary": paper.get("abstract") or paper.get("match_reason"),
                "match_reason": paper.get("match_reason"),
            }
        )

    for index, protocol in enumerate(protocols, start=1):
        evidence_items.append(
            {
                "source_id": _evidence_id("protocol", protocol, index),
                "kind": "protocol",
                "title": protocol.get("title"),
                "year": protocol.get("year"),
                "url": protocol.get("url"),
                "description": protocol.get("description"),
                "steps_preview": protocol.get("steps_preview") or [],
                "materials_preview": protocol.get("materials_preview") or [],
                "match_reason": protocol.get("match_reason"),
            }
        )

    return {
        "items": evidence_items,
        "source_ids": [item["source_id"] for item in evidence_items],
        "source_labels": [
            f"{item['source_id']} - {item.get('title') or 'Untitled evidence'}"
            for item in evidence_items
        ],
    }


def protocol_generation_model() -> str:
    return os.getenv("OPENAI_PROTOCOL_MODEL") or DEFAULT_PROTOCOL_MODEL


def protocol_reasoning_effort() -> str:
    return os.getenv("OPENAI_PROTOCOL_REASONING_EFFORT") or DEFAULT_PROTOCOL_REASONING_EFFORT


def protocol_max_completion_tokens() -> int:
    raw_value = os.getenv("OPENAI_PROTOCOL_MAX_COMPLETION_TOKENS")
    if not raw_value:
        return DEFAULT_PROTOCOL_MAX_COMPLETION_TOKENS
    try:
        return max(4000, int(raw_value))
    except ValueError:
        return DEFAULT_PROTOCOL_MAX_COMPLETION_TOKENS


def protocol_generation_backend() -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "local_fallback_no_openai_key"
    try:
        import instructor  # noqa: F401
    except Exception:
        return "local_fallback_no_instructor"
    return "openai_instructor"


def protocol_agent_context_summary(
    protocol_evidence: list[ExtractedProtocolEvidence],
    prior_memories: list[FeedbackMemoryReference],
    reference_examples: list[CorpusExampleReference],
    safety_review: SafetyReview,
    validated_entities: list[EntityValidation],
) -> dict[str, Any]:
    missing_fields = sorted(
        {
            missing
            for evidence in protocol_evidence
            for missing in evidence.missing_fields
        }
    )
    return {
        "context_roles": PROTOCOL_CONTEXT_ROLES,
        "selected_evidence": {
            "selected_protocols_processed": len(protocol_evidence),
            "steps_extracted": sum(len(item.steps) for item in protocol_evidence),
            "materials_extracted": sum(len(item.materials) for item in protocol_evidence),
            "validation_methods_found": sum(len(item.validation_methods) for item in protocol_evidence),
            "missing_fields": missing_fields,
            "protocol_source_ids": [item.source_id for item in protocol_evidence],
        },
        "prior_feedback": {
            "accepted_feedback_memories": len(prior_memories),
            "sections": sorted({memory.section for memory in prior_memories if memory.section}),
            "memory_text": [memory.memory_text for memory in prior_memories[:5]],
        },
        "structure_references": {
            "structure_examples_retrieved": len(reference_examples),
            "allowed_use": "structure guidance only",
            "structure_notes": [
                {
                    "source": example.source,
                    "experiment_type": example.experiment_type,
                    "notes": example.structure_notes[:3],
                }
                for example in reference_examples[:5]
            ],
        },
        "safety_review": safety_review.model_dump(),
        "entity_normalization": [item.model_dump() for item in validated_entities],
        "source_hierarchy": [
            "selected_protocols_primary",
            "lab_context_constraints_if_present",
            "accepted_feedback_memory",
            "corpus_examples_structure_only",
            "papers_background_only",
            "safety_rules_override_all",
        ],
    }


def _section(
    title: str,
    content: str,
    source_ids: list[str],
    confidence: float,
    assumptions: list[str] | None = None,
    missing_information: list[str] | None = None,
    items: list[MaterialItem] | None = None,
    phases: list[WorkflowPhase] | None = None,
) -> ProtocolSection:
    return ProtocolSection(
        title=title,
        content=content,
        source_ids=source_ids,
        assumptions=assumptions or [],
        missing_information=missing_information or [],
        confidence=confidence,
        items=items or [],
        phases=phases or [],
    )


def _contains_any(haystack: str, needles: list[str]) -> bool:
    lowered = haystack.lower()
    return any(needle.lower() in lowered for needle in needles if needle)


def _evidence_text(evidence_items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in evidence_items:
        parts.extend(
            [
                _safe_text(item.get("title")),
                _safe_text(item.get("summary")),
                _safe_text(item.get("description")),
                _safe_text(item.get("steps_preview")),
                _safe_text(item.get("materials_preview")),
                _safe_text(item.get("match_reason")),
            ]
        )
    return " ".join(part for part in parts if part)


def _protocol_evidence_text(protocol_evidence: list[ExtractedProtocolEvidence]) -> str:
    parts: list[str] = []
    for evidence in protocol_evidence:
        parts.extend(
            [
                evidence.title,
                " ".join(evidence.steps),
                " ".join(evidence.materials),
                " ".join(evidence.equipment),
                " ".join(evidence.conditions),
                " ".join(evidence.validation_methods),
                " ".join(evidence.warnings),
            ]
        )
    return " ".join(part for part in parts if part)


def _material_lines(protocols: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for protocol in protocols:
        for material in protocol.get("materials_preview") or []:
            cleaned = _safe_text(material)
            if cleaned and cleaned.lower() not in {line.lower() for line in lines}:
                lines.append(cleaned)
    return lines[:12]


def _material_items(protocol_evidence: list[ExtractedProtocolEvidence]) -> list[MaterialItem]:
    items: list[MaterialItem] = []
    seen: set[str] = set()
    for evidence in protocol_evidence:
        for material in evidence.materials:
            key = material.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(
                MaterialItem(
                    name=material,
                    source_ids=[evidence.source_id],
                    missing_information=[],
                )
            )
            if len(items) >= 16:
                return items
    return items


def _workflow_lines(protocols: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for protocol in protocols:
        for step in protocol.get("steps_preview") or []:
            cleaned = _safe_text(step)
            if cleaned and cleaned.lower() not in {line.lower() for line in lines}:
                lines.append(cleaned)
    return lines[:10]


def _phase_name_for_step(step: str) -> str:
    lowered = step.lower()
    if any(term in lowered for term in ["induction", "neural induction"]):
        return "Induction"
    if any(term in lowered for term in ["maturation", "mature"]):
        return "Maturation"
    if any(term in lowered for term in ["validate", "validation", "marker", "assay", "stain"]):
        return "Validation"
    if any(term in lowered for term in ["prepare", "plate", "seed", "culture"]):
        return "Preparation"
    return "Workflow"


def _workflow_phases(protocol_evidence: list[ExtractedProtocolEvidence]) -> list[WorkflowPhase]:
    grouped: dict[str, WorkflowPhase] = {}
    step_number = 1
    for evidence in protocol_evidence:
        for step in evidence.steps[:12]:
            phase_name = _phase_name_for_step(step)
            phase = grouped.setdefault(
                phase_name,
                WorkflowPhase(
                    phase_name=phase_name,
                    purpose=f"Review {phase_name.lower()} elements supported by selected protocols.",
                    steps=[],
                    source_ids=[],
                ),
            )
            if evidence.source_id not in phase.source_ids:
                phase.source_ids.append(evidence.source_id)
            phase.steps.append(
                WorkflowStep(
                    step_number=step_number,
                    action=step,
                    parameters=WorkflowParameters(),
                    source_ids=[evidence.source_id],
                    assumptions=["Parameter fields remain blank unless selected protocol evidence explicitly supports them."],
                    missing_information=["Exact execution parameters require qualified researcher review."],
                )
            )
            step_number += 1
    return list(grouped.values())


def _experiment_type(hypothesis: dict[str, Any]) -> str:
    candidates = [
        hypothesis.get("assay"),
        hypothesis.get("mechanism"),
        hypothesis.get("intervention"),
        hypothesis.get("outcome"),
        hypothesis.get("domain"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower().replace(" ", "_").replace("/", "_")
    return "custom_protocol"


def _draft_title(hypothesis: dict[str, Any]) -> str:
    model = hypothesis.get("model_system")
    intervention = hypothesis.get("intervention")
    outcome = hypothesis.get("outcome")
    parts = [part for part in [model, intervention, outcome] if part]
    if parts:
        return "Researcher-review protocol draft: " + " / ".join(str(part) for part in parts[:3])
    return "Researcher-review protocol draft"


def _fallback_protocol_draft(
    session: dict[str, Any],
    prior_memories: list[FeedbackMemoryReference],
    reference_examples: list[CorpusExampleReference] | None = None,
    protocol_evidence: list[ExtractedProtocolEvidence] | None = None,
    safety_review: SafetyReview | None = None,
    validated_entities: list[EntityValidation] | None = None,
    generation_error: str | None = None,
) -> CustomProtocolDraft:
    hypothesis = session.get("structured_hypothesis") or {}
    evidence_pack = build_evidence_pack(session)
    protocol_evidence = protocol_evidence or []
    reference_examples = reference_examples or []
    protocol_source_ids = [item.source_id for item in protocol_evidence]
    paper_source_ids = [
        item["source_id"]
        for item in evidence_pack["items"]
        if item.get("kind") == "paper"
    ]
    source_ids = protocol_source_ids or evidence_pack["source_ids"]
    evidence_text = _protocol_evidence_text(protocol_evidence) or _evidence_text(evidence_pack["items"])
    protocols = session.get("selected_protocols") or []
    material_items = _material_items(protocol_evidence)
    materials = [item.name for item in material_items] or _material_lines(protocols)
    workflow_phases = _workflow_phases(protocol_evidence)
    workflow = [
        step.action
        for phase in workflow_phases
        for step in phase.steps
    ] or _workflow_lines(protocols)
    safety_review = safety_review or SafetyReview()
    validated_entities = validated_entities or []
    generation_backend = "local_fallback_openai_error" if generation_error else protocol_generation_backend()

    model_system = hypothesis.get("model_system")
    intervention = hypothesis.get("intervention")
    outcome = hypothesis.get("outcome")
    assay = hypothesis.get("assay")
    control = hypothesis.get("control")

    material_content = (
        "Materials and reagents mentioned by selected protocols: " + "; ".join(materials)
        if materials
        else "missing information. The selected protocol evidence does not include enough material or reagent detail."
    )
    workflow_content = (
        "High-level workflow elements found in selected protocols: " + " ".join(f"{index}. {line}" for index, line in enumerate(workflow, start=1))
        if workflow
        else "missing information. The selected evidence does not include enough protocol step detail to produce an adapted workflow."
    )
    if safety_review.risk_level == "blocked_or_redacted":
        workflow_content = (
            "blocked_or_redacted. The safety classifier flagged this request, so operational workflow details are not generated. "
            "Only high-level review by qualified personnel is appropriate."
        )
    controls_content = (
        f"The hypothesis names this comparison/control: {control}. The researcher should verify that selected evidence supports this control before execution."
        if control and _contains_any(evidence_text, [control])
        else "missing information. Selected evidence does not clearly specify controls for this custom protocol."
    )
    validation_content = (
        f"Potential validation/readout from the structured hypothesis: {assay or outcome}. Confirm marker, assay, timing and acceptance criteria from selected evidence before execution."
        if assay or outcome
        else "missing information. Selected evidence does not specify a validation readout."
    )

    memory_notes = [memory.memory_text for memory in prior_memories[:3]]
    if memory_notes:
        workflow_content = workflow_content + " Prior researcher feedback to consider: " + " ".join(memory_notes)
        validation_content = validation_content + " Prior researcher feedback to consider: " + " ".join(memory_notes)

    missing_common = []
    if not source_ids:
        missing_common.append("No selected papers or protocols were provided.")
    if not protocols:
        missing_common.append("No selected protocol records were provided.")

    return CustomProtocolDraft(
        title=_draft_title(hypothesis),
        goal=(
            "Create a researcher-review draft grounded primarily in selected protocols"
            f" for {model_system or 'the stated model system'} and {intervention or 'the stated intervention'}."
        ),
        experiment_type=_experiment_type(hypothesis),
        source_evidence_used=evidence_pack["source_labels"],
        scientific_rationale=_section(
            "Scientific rationale",
            (
                "The selected evidence is relevant to the stated hypothesis. "
                f"Model system: {model_system or 'missing information'}; "
                f"intervention: {intervention or 'missing information'}; "
                f"outcome: {outcome or 'missing information'}. "
                "This draft does not add unsupported experimental details."
            ),
            source_ids + paper_source_ids,
            0.55 if source_ids else 0.2,
            missing_information=missing_common,
        ),
        materials_and_reagents=_section(
            "Materials and reagents",
            material_content,
            source_ids,
            0.65 if materials else 0.25,
            missing_information=[] if materials else ["Materials/reagents are not present in the selected evidence payload."],
            items=material_items,
        ),
        adapted_workflow=_section(
            "Adapted workflow",
            workflow_content,
            source_ids,
            0.6 if workflow else 0.25,
            assumptions=["Workflow must remain a researcher-review draft until verified by qualified personnel."],
            missing_information=[] if workflow else ["Protocol step detail is missing from selected evidence."],
            phases=workflow_phases,
        ),
        controls=_section(
            "Controls",
            controls_content,
            source_ids if control and _contains_any(evidence_text, [control]) else [],
            0.55 if control and _contains_any(evidence_text, [control]) else 0.25,
            missing_information=[] if control and _contains_any(evidence_text, [control]) else ["Control design is not sufficiently supported by selected evidence."],
        ),
        validation_readout=_section(
            "Validation/readout",
            validation_content,
            source_ids if assay or outcome else [],
            0.5 if assay or outcome else 0.2,
            missing_information=["Acceptance criteria and exact readout parameters require researcher review."],
        ),
        safety_review=safety_review,
        risks_and_limitations=_section(
            "Risks and limitations",
            (
                "This is not an executable SOP. Missing or weakly supported details should remain flagged instead of being filled in by the model. "
                "Key risks include overgeneralizing from similar evidence, missing protocol-specific timing, using insufficient validation criteria, "
                f"and safety review status: {safety_review.risk_level}."
            ),
            source_ids,
            0.6 if source_ids else 0.3,
            missing_information=missing_common,
        ),
        open_questions=[
            "Which selected protocol is the primary workflow template?",
            "What equipment, biosafety level, and lab constraints must be enforced?",
            "Which validation readout is required before the protocol can be considered acceptable?",
        ],
        prior_feedback_used=prior_memories,
        reference_examples_used=reference_examples,
        validated_entities=validated_entities,
        extracted_protocol_evidence=protocol_evidence,
        generation_backend=generation_backend,
        generation_model=protocol_generation_model(),
        reasoning_effort=protocol_reasoning_effort(),
        generation_error=generation_error,
    )


def _generation_prompt(
    session: dict[str, Any],
    prior_memories: list[FeedbackMemoryReference],
    reference_examples: list[CorpusExampleReference] | None = None,
    protocol_evidence: list[ExtractedProtocolEvidence] | None = None,
    safety_review: SafetyReview | None = None,
    validated_entities: list[EntityValidation] | None = None,
    previous_version: ProtocolVersionResponse | None = None,
    feedback: list[ProtocolFeedbackResponse] | None = None,
) -> list[dict[str, str]]:
    evidence_pack = build_evidence_pack(session)
    protocol_evidence = protocol_evidence or []
    reference_examples = reference_examples or []
    safety_review = safety_review or SafetyReview()
    validated_entities = validated_entities or []
    agent_context = protocol_agent_context_summary(
        protocol_evidence=protocol_evidence,
        prior_memories=prior_memories,
        reference_examples=reference_examples,
        safety_review=safety_review,
        validated_entities=validated_entities,
    )
    task = "Generate a structured researcher-review protocol draft."
    if previous_version:
        task = "Revise the structured researcher-review protocol draft using the researcher feedback."

    return [
        {
            "role": "system",
            "content": (
                "You are the protocol_composer_agent in an agentic scientific planning system. "
                "Parallel specialist modules have already prepared selected-evidence extraction, prior feedback retrieval, "
                "structure references, safety review, and entity normalization context. "
                "You generate structured protocol drafts for qualified researcher review. "
                "Return only valid data for the provided Pydantic schema. "
                "Selected protocols are the primary grounding source for materials, workflow, controls, and validation. "
                "Corpus examples are structure guidance only and must never override selected protocols. "
                "Prior feedback memory may shape how similar sections are framed, but it is not primary evidence. "
                "Papers, if present, are background/rationale only unless they clearly contain method detail. "
                "Safety review output overrides every other source. "
                "If information is missing, write 'missing information'. "
                "Do not invent unsupported parameters or executable lab details. Keep the draft high-level and non-executable."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{task}\n\n"
                f"Original query:\n{session.get('original_query')}\n\n"
                f"Structured hypothesis:\n{session.get('structured_hypothesis')}\n\n"
                "Context bundle:\n"
                f"{json.dumps(agent_context, ensure_ascii=False, indent=2)}\n\n"
                f"Selected protocol evidence pack:\n{[item.model_dump() for item in protocol_evidence]}\n\n"
                f"Optional selected paper/background evidence:\n{[item for item in evidence_pack['items'] if item.get('kind') == 'paper']}\n\n"
                f"Previous version:\n{previous_version.protocol.model_dump() if previous_version else None}\n\n"
                f"Previous validation report:\n{previous_version.validation_report.model_dump() if previous_version and previous_version.validation_report else None}\n\n"
                f"Researcher feedback:\n{[item.model_dump() for item in feedback or []]}\n\n"
                "Composer requirements:\n"
                "- Use selected protocol source_ids for every major protocol-building section when supported.\n"
                "- Mark missing details as missing information instead of filling them in.\n"
                "- Use corpus examples only for internal structure guidance; do not quote, name, or summarize them in user-visible protocol sections.\n"
                "- Keep corpus examples out of source_ids unless they are explicitly represented as structure notes.\n"
                "- If safety risk is blocked_or_redacted, do not provide operational workflow detail.\n"
                "- Preserve prior_feedback_used, reference_examples_used, validated_entities, and extracted_protocol_evidence in the schema output.\n\n"
                "Required disclaimer: Researcher-review draft. Must be reviewed by qualified personnel before execution."
            ),
        },
    ]


def _try_instructor_draft(
    session: dict[str, Any],
    prior_memories: list[FeedbackMemoryReference],
    reference_examples: list[CorpusExampleReference] | None = None,
    protocol_evidence: list[ExtractedProtocolEvidence] | None = None,
    safety_review: SafetyReview | None = None,
    validated_entities: list[EntityValidation] | None = None,
    previous_version: ProtocolVersionResponse | None = None,
    feedback: list[ProtocolFeedbackResponse] | None = None,
) -> tuple[CustomProtocolDraft | None, str | None]:
    if not os.getenv("OPENAI_API_KEY"):
        return None, "OPENAI_API_KEY is not configured."
    try:
        import instructor
    except Exception as exc:
        return None, f"Instructor import failed: {type(exc).__name__}: {exc}"

    model = protocol_generation_model()
    reasoning_effort = protocol_reasoning_effort()
    max_completion_tokens = protocol_max_completion_tokens()
    try:
        messages = _generation_prompt(
            session,
            prior_memories,
            reference_examples,
            protocol_evidence,
            safety_review,
            validated_entities,
            previous_version,
            feedback,
        )
        if hasattr(instructor, "from_provider"):
            client = instructor.from_provider(f"openai/{model}")
            draft = client.create(
                response_model=CustomProtocolDraft,
                messages=messages,
                max_retries=2,
                max_completion_tokens=max_completion_tokens,
                reasoning_effort=reasoning_effort,
            )
        else:
            from openai import OpenAI

            client = instructor.from_openai(OpenAI())
            draft = client.chat.completions.create(
                model=model,
                response_model=CustomProtocolDraft,
                messages=messages,
                max_retries=2,
                max_completion_tokens=max_completion_tokens,
                reasoning_effort=reasoning_effort,
            )
    except Exception as exc:
        message = f"OpenAI Instructor generation failed: {type(exc).__name__}: {exc}"
        return None, message[:500]
    draft.generation_backend = "openai_instructor"
    draft.generation_model = model
    draft.reasoning_effort = reasoning_effort
    draft.generation_error = None
    return draft, None


def generate_protocol_draft(
    session: dict[str, Any],
    prior_memories: list[FeedbackMemoryReference],
    reference_examples: list[CorpusExampleReference] | None = None,
    protocol_evidence: list[ExtractedProtocolEvidence] | None = None,
    safety_review: SafetyReview | None = None,
    validated_entities: list[EntityValidation] | None = None,
) -> CustomProtocolDraft:
    instructor_draft, generation_error = _try_instructor_draft(
        session,
        prior_memories,
        reference_examples,
        protocol_evidence,
        safety_review,
        validated_entities,
    )
    if instructor_draft:
        instructor_draft.prior_feedback_used = prior_memories
        instructor_draft.reference_examples_used = reference_examples or instructor_draft.reference_examples_used
        instructor_draft.safety_review = safety_review or instructor_draft.safety_review
        instructor_draft.validated_entities = validated_entities or instructor_draft.validated_entities
        instructor_draft.extracted_protocol_evidence = protocol_evidence or instructor_draft.extracted_protocol_evidence
        instructor_draft.generation_backend = "openai_instructor"
        instructor_draft.generation_model = protocol_generation_model()
        instructor_draft.reasoning_effort = protocol_reasoning_effort()
        instructor_draft.generation_error = None
        return instructor_draft
    return _fallback_protocol_draft(
        session,
        prior_memories,
        reference_examples,
        protocol_evidence,
        safety_review,
        validated_entities,
        generation_error,
    )


def _append_feedback_to_section(section: ProtocolSection, feedback_items: list[ProtocolFeedbackResponse]) -> ProtocolSection:
    actionable = [
        item
        for item in feedback_items
        if item.feedback_type in {"correction", "comment", "rejection"} and (item.feedback_text or "").strip()
    ]
    if not actionable:
        return section

    additions = []
    missing = list(section.missing_information)
    for item in actionable:
        label = "Researcher correction" if item.feedback_type == "correction" else "Researcher note"
        if item.feedback_type == "rejection":
            label = "Researcher rejection"
            missing.append("This section requires substantial rewrite before acceptance.")
        reason = f" Reason: {item.reason}" if item.reason else ""
        additions.append(f"{label}: {item.feedback_text}.{reason}")

    return section.model_copy(
        update={
            "content": f"{section.content}\n\n" + "\n".join(additions),
            "missing_information": missing,
            "confidence": max(0.1, min(1.0, section.confidence + 0.05)),
        }
    )


def _fallback_revised_protocol(
    session: dict[str, Any],
    prior_memories: list[FeedbackMemoryReference],
    previous_version: ProtocolVersionResponse,
    feedback: list[ProtocolFeedbackResponse],
    reference_examples: list[CorpusExampleReference] | None = None,
    protocol_evidence: list[ExtractedProtocolEvidence] | None = None,
    safety_review: SafetyReview | None = None,
    validated_entities: list[EntityValidation] | None = None,
    generation_error: str | None = None,
) -> tuple[CustomProtocolDraft, str]:
    draft = previous_version.protocol.model_copy(deep=True)
    by_section: dict[str, list[ProtocolFeedbackResponse]] = {}
    for item in feedback:
        by_section.setdefault(item.section, []).append(item)

    updates: dict[str, Any] = {
        "prior_feedback_used": prior_memories,
        "reference_examples_used": reference_examples or draft.reference_examples_used,
        "safety_review": safety_review or draft.safety_review,
        "validated_entities": validated_entities or draft.validated_entities,
        "extracted_protocol_evidence": protocol_evidence or draft.extracted_protocol_evidence,
        "generation_backend": "local_fallback_openai_error" if generation_error else protocol_generation_backend(),
        "generation_model": protocol_generation_model(),
        "reasoning_effort": protocol_reasoning_effort(),
        "generation_error": generation_error,
    }
    changed_sections: list[str] = []
    for key in SECTION_KEYS:
        section_feedback = by_section.get(key) or []
        if not section_feedback:
            continue
        current_section = getattr(draft, key)
        updated_section = _append_feedback_to_section(current_section, section_feedback)
        updates[key] = updated_section
        if updated_section != current_section:
            changed_sections.append(current_section.title)

    if prior_memories:
        workflow = updates.get("adapted_workflow", draft.adapted_workflow)
        memory_text = " ".join(memory.memory_text for memory in prior_memories[:3])
        updates["adapted_workflow"] = workflow.model_copy(
            update={
                "content": f"{workflow.content}\n\nRelevant reusable feedback memory: {memory_text}",
                "confidence": min(1.0, workflow.confidence + 0.03),
            }
        )
        if "Adapted workflow" not in changed_sections:
            changed_sections.append("Adapted workflow")

    if previous_version.validation_report and previous_version.validation_report.issues:
        risk_section = updates.get("risks_and_limitations", draft.risks_and_limitations)
        issue_text = " ".join(
            f"{issue.section}: {issue.issue} Suggestion: {issue.suggestion}"
            for issue in previous_version.validation_report.issues[:4]
        )
        updates["risks_and_limitations"] = risk_section.model_copy(
            update={
                "content": f"{risk_section.content}\n\nValidation review findings to address: {issue_text}",
                "missing_information": list(
                    dict.fromkeys(
                        [
                            *risk_section.missing_information,
                            *previous_version.validation_report.missing_information,
                        ]
                    )
                ),
            }
        )
        if "Risks and limitations" not in changed_sections:
            changed_sections.append("Risks and limitations")

    updated_draft = draft.model_copy(update=updates)
    summary = (
        "Revised sections: " + ", ".join(changed_sections)
        if changed_sections
        else "No section text changed because no actionable correction/comment/rejection feedback was provided."
    )
    return updated_draft, summary


def revise_protocol_draft(
    session: dict[str, Any],
    prior_memories: list[FeedbackMemoryReference],
    previous_version: ProtocolVersionResponse,
    feedback: list[ProtocolFeedbackResponse],
    reference_examples: list[CorpusExampleReference] | None = None,
    protocol_evidence: list[ExtractedProtocolEvidence] | None = None,
    safety_review: SafetyReview | None = None,
    validated_entities: list[EntityValidation] | None = None,
) -> tuple[CustomProtocolDraft, str]:
    instructor_draft, generation_error = _try_instructor_draft(
        session,
        prior_memories,
        reference_examples,
        protocol_evidence,
        safety_review,
        validated_entities,
        previous_version,
        feedback,
    )
    if instructor_draft:
        instructor_draft.prior_feedback_used = prior_memories
        instructor_draft.reference_examples_used = reference_examples or instructor_draft.reference_examples_used
        instructor_draft.safety_review = safety_review or instructor_draft.safety_review
        instructor_draft.validated_entities = validated_entities or instructor_draft.validated_entities
        instructor_draft.extracted_protocol_evidence = protocol_evidence or instructor_draft.extracted_protocol_evidence
        instructor_draft.generation_backend = "openai_instructor"
        instructor_draft.generation_model = protocol_generation_model()
        instructor_draft.reasoning_effort = protocol_reasoning_effort()
        instructor_draft.generation_error = None
        return instructor_draft, "Revised protocol using researcher feedback and relevant feedback memory."
    return _fallback_revised_protocol(
        session,
        prior_memories,
        previous_version,
        feedback,
        reference_examples,
        protocol_evidence,
        safety_review,
        validated_entities,
        generation_error,
    )
