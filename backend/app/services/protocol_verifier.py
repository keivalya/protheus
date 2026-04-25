from __future__ import annotations

from app.services.protocol_models import (
    CustomProtocolDraft,
    ExtractedProtocolEvidence,
    ProtocolSection,
    ProtocolVerifierReport,
)

MAJOR_SECTIONS = [
    "scientific_rationale",
    "materials_and_reagents",
    "adapted_workflow",
    "controls",
    "validation_readout",
    "risks_and_limitations",
]


def _section_missing_marker(section: ProtocolSection) -> bool:
    content = section.content.lower()
    return "missing information" in content or bool(section.missing_information)


def verify_protocol_draft(
    protocol: CustomProtocolDraft,
    protocol_evidence: list[ExtractedProtocolEvidence],
) -> ProtocolVerifierReport:
    available_protocol_source_ids = {item.source_id for item in protocol_evidence}
    warnings: list[str] = []
    unsupported_sections: list[str] = []

    if not protocol.disclaimer:
        warnings.append("Missing researcher-review disclaimer.")

    if protocol.safety_review.risk_level != "low_risk" and not protocol.safety_review.requires_expert_review:
        warnings.append("Safety review flags risk but does not require expert review.")

    if not protocol.open_questions:
        warnings.append("No open questions were provided for researcher review.")

    for section_name in MAJOR_SECTIONS:
        section = getattr(protocol, section_name)
        source_ids = set(section.source_ids)
        protocol_source_ids = source_ids & available_protocol_source_ids
        if not source_ids and not _section_missing_marker(section):
            unsupported_sections.append(section_name)
            continue
        if section_name not in {"scientific_rationale", "risks_and_limitations"}:
            if not protocol_source_ids and not _section_missing_marker(section):
                unsupported_sections.append(section_name)
        if section.confidence > 0.8 and _section_missing_marker(section):
            warnings.append(f"{section_name} has high confidence despite missing information.")

    if protocol.safety_review.risk_level == "blocked_or_redacted":
        warnings.append("Blocked or redacted request: operational detail should not be generated.")

    passed = not unsupported_sections and protocol.disclaimer != "" and bool(protocol.open_questions)
    return ProtocolVerifierReport(
        passed=passed,
        warnings=warnings,
        unsupported_sections=unsupported_sections,
        safety_flags=protocol.safety_review.flags,
    )

