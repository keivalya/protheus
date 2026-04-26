from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.protocol_models import (
    CustomProtocolDraft,
    ExtractedProtocolEvidence,
    FeedbackMemoryReference,
    ProtocolSection,
    ProtocolValidationIssue,
    ProtocolValidationReport,
)

RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "validation_rules.json"

MAJOR_SECTION_NAMES = [
    "scientific_rationale",
    "materials_and_reagents",
    "adapted_workflow",
    "controls",
    "validation_readout",
    "risks_and_limitations",
]

SECTION_LABELS = {
    "scientific_rationale": "Scientific rationale",
    "materials_and_reagents": "Materials and reagents",
    "adapted_workflow": "Adapted workflow",
    "controls": "Controls",
    "validation_readout": "Validation/readout",
    "risks_and_limitations": "Risks and limitations",
}


def _load_rules() -> dict[str, Any]:
    try:
        with RULES_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _rules_for_domain(domain: str | None) -> dict[str, Any]:
    rules = _load_rules()
    if not rules:
        return {}
    if domain and domain in rules:
        return {**rules.get("default", {}), **rules[domain]}
    return rules.get("default", {})


def _protocol_source_ids(evidence: list[ExtractedProtocolEvidence]) -> set[str]:
    return {item.source_id for item in evidence}


def _section_is_missing(section: ProtocolSection) -> bool:
    return "missing information" in section.content.lower() or bool(section.missing_information)


def _score_grounding(
    protocol: CustomProtocolDraft,
    protocol_evidence: list[ExtractedProtocolEvidence],
    issues: list[ProtocolValidationIssue],
) -> float:
    allowed_source_ids = _protocol_source_ids(protocol_evidence)
    scored_sections = 0
    grounded_sections = 0

    for section_name in MAJOR_SECTION_NAMES:
        section = getattr(protocol, section_name)
        scored_sections += 1
        section_source_ids = set(section.source_ids)
        supported_by_protocol = bool(section_source_ids & allowed_source_ids)
        explicitly_missing = _section_is_missing(section)

        if supported_by_protocol or explicitly_missing:
            grounded_sections += 1
        else:
            issues.append(
                ProtocolValidationIssue(
                    section=section_name,
                    severity="high",
                    issue=f"{SECTION_LABELS[section_name]} is not grounded in selected protocol source_ids.",
                    suggestion="Add selected protocol source_ids or mark unsupported content as missing information.",
                    requires_researcher_review=True,
                )
            )

        unsupported_ids = sorted(section_source_ids - allowed_source_ids)
        paper_or_memory_ids = [
            source_id
            for source_id in unsupported_ids
            if source_id.startswith("paper:") or source_id.startswith("memory:")
        ]
        if section_name not in {"scientific_rationale", "risks_and_limitations"} and paper_or_memory_ids:
            issues.append(
                ProtocolValidationIssue(
                    section=section_name,
                    severity="medium",
                    issue="A protocol-building section relies on paper or memory IDs instead of selected protocol IDs.",
                    suggestion="Use papers/memory only for rationale or review notes; ground protocol details in selected protocols.",
                    requires_researcher_review=True,
                )
            )

    if scored_sections == 0:
        return 0.0
    return grounded_sections / scored_sections


def _is_empty_section(protocol: CustomProtocolDraft, section_name: str) -> bool:
    value = getattr(protocol, section_name, None)
    if isinstance(value, ProtocolSection):
        return not value.content.strip() and not value.items and not value.phases
    if isinstance(value, list):
        return not value
    if isinstance(value, str):
        return not value.strip()
    return value is None


def _score_completeness(
    protocol: CustomProtocolDraft,
    rules: dict[str, Any],
    issues: list[ProtocolValidationIssue],
) -> float:
    required_sections = rules.get("required_sections") or []
    if not required_sections:
        required_sections = [
            "title",
            "goal",
            "materials_and_reagents",
            "adapted_workflow",
            "controls",
            "validation_readout",
            "risks_and_limitations",
            "open_questions",
        ]

    present = 0
    for section_name in required_sections:
        if not _is_empty_section(protocol, section_name):
            present += 1
        else:
            issues.append(
                ProtocolValidationIssue(
                    section=section_name,
                    severity="high",
                    issue=f"Required section '{section_name}' is missing or empty.",
                    suggestion="Add this section or explicitly mark missing information for researcher review.",
                    requires_researcher_review=True,
                )
            )

    if not protocol.materials_and_reagents.items and not protocol.materials_and_reagents.missing_information:
        issues.append(
            ProtocolValidationIssue(
                section="materials_and_reagents",
                severity="medium",
                issue="Materials section has no structured items and no missing-information explanation.",
                suggestion="Extract materials from selected protocols or mark materials as missing information.",
                requires_researcher_review=True,
            )
        )

    if not protocol.adapted_workflow.phases and not protocol.adapted_workflow.missing_information:
        issues.append(
            ProtocolValidationIssue(
                section="adapted_workflow",
                severity="medium",
                issue="Workflow section has no structured phases and no missing-information explanation.",
                suggestion="Extract workflow phases from selected protocols or mark workflow detail as missing information.",
                requires_researcher_review=True,
            )
        )

    if not required_sections:
        return 0.0
    return present / len(required_sections)


def _check_vague_or_missing(
    protocol: CustomProtocolDraft,
    rules: dict[str, Any],
    issues: list[ProtocolValidationIssue],
) -> list[str]:
    missing_information: list[str] = []
    vague_phrases = [str(item).lower() for item in rules.get("vague_phrases") or []]

    for section_name in MAJOR_SECTION_NAMES:
        section = getattr(protocol, section_name)
        missing_information.extend(
            f"{SECTION_LABELS[section_name]}: {item}"
            for item in section.missing_information
        )

        content = section.content.lower()
        for phrase in vague_phrases:
            if phrase and phrase in content:
                issues.append(
                    ProtocolValidationIssue(
                        section=section_name,
                        severity="medium",
                        issue=f"Section contains vague phrase: '{phrase}'.",
                        suggestion="Replace vague wording with sourced detail or mark the detail as missing information.",
                        requires_researcher_review=True,
                    )
                )

        if re.search(r"\b(?:validate|measure|confirm|check)\b", content) and not (
            section.source_ids or section.missing_information
        ):
            issues.append(
                ProtocolValidationIssue(
                    section=section_name,
                    severity="medium",
                    issue="Section mentions validation or measurement without source support or missing-information notes.",
                    suggestion="Specify the source-supported readout or ask the researcher to provide it.",
                    requires_researcher_review=True,
                )
            )

    if not protocol.controls.source_ids and not protocol.controls.missing_information:
        missing_information.append("Control condition")
    if not protocol.validation_readout.source_ids and not protocol.validation_readout.missing_information:
        missing_information.append("Specific validation assay or marker-based readout")

    return list(dict.fromkeys(item for item in missing_information if item))


def _check_step_structure(
    protocol: CustomProtocolDraft,
    issues: list[ProtocolValidationIssue],
) -> None:
    phases = protocol.adapted_workflow.phases
    if not phases:
        return

    order = [phase.phase_name.lower() for phase in phases]
    validation_index = next((index for index, name in enumerate(order) if "validation" in name), None)
    preparation_index = next((index for index, name in enumerate(order) if "preparation" in name), None)
    if validation_index is not None and preparation_index is not None and validation_index < preparation_index:
        issues.append(
            ProtocolValidationIssue(
                section="adapted_workflow",
                severity="medium",
                issue="Validation phase appears before preparation.",
                suggestion="Review workflow phase ordering before accepting this draft.",
                requires_researcher_review=True,
            )
        )

    for phase in phases:
        if not phase.source_ids:
            issues.append(
                ProtocolValidationIssue(
                    section="adapted_workflow",
                    severity="medium",
                    issue=f"Workflow phase '{phase.phase_name}' has no source_ids.",
                    suggestion="Attach selected protocol source_ids to each workflow phase.",
                    requires_researcher_review=True,
                )
            )


def _check_required_validation_items(
    protocol: CustomProtocolDraft,
    rules: dict[str, Any],
    issues: list[ProtocolValidationIssue],
) -> None:
    required_items = [str(item).lower() for item in rules.get("required_validation_items") or []]
    haystack = " ".join(
        [
            protocol.controls.content,
            protocol.validation_readout.content,
            " ".join(protocol.controls.missing_information),
            " ".join(protocol.validation_readout.missing_information),
            " ".join(protocol.open_questions),
        ]
    ).lower()

    for item in required_items:
        if item in {"missing information list", "researcher-review disclaimer"}:
            continue
        normalized_tokens = [token for token in re.findall(r"[a-z0-9]+", item) if len(token) > 2]
        if normalized_tokens and not any(token in haystack for token in normalized_tokens):
            issues.append(
                ProtocolValidationIssue(
                    section="validation_readout" if "readout" in item or "assay" in item else "controls",
                    severity="medium",
                    issue=f"Expected validation item is not clearly represented: {item}.",
                    suggestion="Ask the researcher to confirm this item or mark it as missing information.",
                    requires_researcher_review=True,
                )
            )


def validate_protocol_draft(
    protocol: CustomProtocolDraft,
    original_query: str,
    structured_hypothesis: dict[str, Any],
    selected_protocols: list[dict[str, Any]],
    protocol_evidence: list[ExtractedProtocolEvidence],
    prior_memories: list[FeedbackMemoryReference],
) -> ProtocolValidationReport:
    del selected_protocols, prior_memories  # Reserved for corpus-backed validation expansion.

    domain = structured_hypothesis.get("domain")
    rules = _rules_for_domain(domain if isinstance(domain, str) else None)
    issues: list[ProtocolValidationIssue] = []

    grounding_score = _score_grounding(protocol, protocol_evidence, issues)
    completeness_score = _score_completeness(protocol, rules, issues)
    missing_information = _check_vague_or_missing(protocol, rules, issues)
    _check_step_structure(protocol, issues)
    _check_required_validation_items(protocol, rules, issues)

    if protocol.safety_review.risk_level == "blocked_or_redacted":
        issues.append(
            ProtocolValidationIssue(
                section="safety_review",
                severity="high",
                issue="Safety classifier marked this request as blocked or redacted.",
                suggestion="Do not show operational protocol details. Route to qualified expert review.",
                requires_researcher_review=True,
            )
        )
    elif protocol.safety_review.requires_expert_review:
        issues.append(
            ProtocolValidationIssue(
                section="safety_review",
                severity="medium",
                issue="Safety classifier marked this draft as requiring expert review.",
                suggestion="Researcher must confirm biosafety, approvals and lab constraints before acceptance.",
                requires_researcher_review=True,
            )
        )

    if not protocol.disclaimer:
        issues.append(
            ProtocolValidationIssue(
                section="disclaimer",
                severity="high",
                issue="Researcher-review disclaimer is missing.",
                suggestion="Add the required qualified-personnel review disclaimer.",
                requires_researcher_review=True,
            )
        )

    high_issue = any(issue.severity == "high" for issue in issues)
    if protocol.safety_review.risk_level == "blocked_or_redacted":
        overall_status = "blocked"
        can_show = False
    elif (
        high_issue
        or protocol.safety_review.requires_expert_review
        or grounding_score < 0.75
        or completeness_score < 0.75
    ):
        overall_status = "needs_revision"
        can_show = True
    else:
        overall_status = "pass"
        can_show = True

    query_text = original_query.lower()
    safety_flags = list(protocol.safety_review.flags)
    for configured_flag in rules.get("safety_flags") or []:
        flag = str(configured_flag)
        if flag.lower() in query_text and flag not in safety_flags:
            safety_flags.append(flag)

    return ProtocolValidationReport(
        overall_status=overall_status,
        grounding_score=round(grounding_score, 3),
        completeness_score=round(completeness_score, 3),
        safety_status=protocol.safety_review.risk_level,
        issues=issues,
        missing_information=missing_information,
        safety_flags=safety_flags,
        can_show_to_researcher=can_show,
    )
