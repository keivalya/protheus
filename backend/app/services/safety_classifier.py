from __future__ import annotations

from typing import Any

from app.services.protocol_models import SafetyReview

BLOCKED_TERMS = {
    "gain of function": "unsafe optimization",
    "increase virulence": "unsafe optimization",
    "enhance virulence": "unsafe optimization",
    "weapon": "weaponization",
    "bioweapon": "weaponization",
    "anthrax": "dangerous pathogen",
    "ebola": "dangerous pathogen",
    "smallpox": "dangerous pathogen",
}

EXPERT_REVIEW_TERMS = {
    "human sample": "human samples",
    "whole blood": "human samples",
    "patient": "human samples",
    "animal": "animal studies",
    "mouse": "animal studies",
    "mice": "animal studies",
    "rat": "animal studies",
    "infectious": "infectious agents",
    "virus": "infectious agents",
    "lentivirus": "viral vector",
    "aav": "viral vector",
    "toxin": "toxins",
    "clinical": "clinical use",
    "recombinant": "recombinant or synthetic nucleic acid work",
    "synthetic nucleic": "recombinant or synthetic nucleic acid work",
    "crispr": "genome editing",
    "bsl-2": "BSL-2 or higher work",
    "bsl2": "BSL-2 or higher work",
    "bsl-3": "BSL-2 or higher work",
    "bsl3": "BSL-2 or higher work",
    "ipsc": "human-derived cell model",
    "hipsc": "human-derived cell model",
}


def _flatten_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            parts.extend(_flatten_text(item) for item in value.values())
        elif isinstance(value, list):
            parts.extend(_flatten_text(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def classify_protocol_safety(
    original_query: str,
    structured_hypothesis: dict[str, Any],
    selected_protocols: list[dict[str, Any]],
    lab_context: dict[str, Any] | None = None,
) -> SafetyReview:
    text = _flatten_text(original_query, structured_hypothesis, selected_protocols, lab_context)

    blocked_flags = sorted({flag for term, flag in BLOCKED_TERMS.items() if term in text})
    if blocked_flags:
        return SafetyReview(
            risk_level="blocked_or_redacted",
            flags=blocked_flags,
            requires_expert_review=True,
            notes=[
                "Do not generate operational details for blocked or unsafe biological work.",
                "Return only high-level review guidance and missing-information prompts.",
            ],
        )

    expert_flags = sorted({flag for term, flag in EXPERT_REVIEW_TERMS.items() if term in text})
    if expert_flags:
        return SafetyReview(
            risk_level="needs_expert_review",
            flags=expert_flags,
            requires_expert_review=True,
            notes=[
                "Generate only a researcher-review draft.",
                "Qualified personnel must verify biosafety, approvals, controls and execution details.",
            ],
        )

    return SafetyReview(
        risk_level="low_risk",
        flags=[],
        requires_expert_review=False,
        notes=["No high-risk signals were detected by the local heuristic safety classifier."],
    )

