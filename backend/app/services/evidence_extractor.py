from __future__ import annotations

import re
from typing import Any

from app.services.protocol_models import ExtractedProtocolEvidence

EQUIPMENT_TERMS = [
    "incubator",
    "centrifuge",
    "microscope",
    "biosafety cabinet",
    "flow cytometer",
    "plate reader",
    "pipette",
    "water bath",
    "cryovial",
]

VALIDATION_TERMS = [
    "immunostaining",
    "marker",
    "qpcr",
    "flow cytometry",
    "microscopy",
    "viability",
    "western blot",
    "assay",
    "readout",
]

WARNING_TERMS = [
    "caution",
    "warning",
    "hazard",
    "toxic",
    "sterile",
    "biosafety",
    "contamination",
]

CONDITION_PATTERN = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s?(?:min|minutes?|h|hours?|days?|weeks?|°c|c|ml|ul|µl|uL|µM|uM|mM|%))\b",
    flags=re.IGNORECASE,
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip(" .;:")


def _source_id(protocol: dict[str, Any], index: int) -> str:
    raw_id = _clean(protocol.get("id") or protocol.get("url") or protocol.get("title"))
    return f"protocol:{raw_id or index}"


def _dedupe(values: list[str], limit: int = 16) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _sentences(text: str) -> list[str]:
    return _dedupe(re.split(r"(?<=[.!?])\s+|\n+", text), limit=20)


def _extract_matching_sentences(text: str, terms: list[str], limit: int = 8) -> list[str]:
    sentences = _sentences(text)
    matches = [
        sentence
        for sentence in sentences
        if any(term.lower() in sentence.lower() for term in terms)
    ]
    return _dedupe(matches, limit=limit)


def extract_protocol_evidence(selected_protocols: list[dict[str, Any]]) -> list[ExtractedProtocolEvidence]:
    extracted: list[ExtractedProtocolEvidence] = []

    for index, protocol in enumerate(selected_protocols, start=1):
        source_id = _source_id(protocol, index)
        steps = _dedupe([_clean(step) for step in protocol.get("steps_preview") or []], limit=20)
        materials = _dedupe([_clean(item) for item in protocol.get("materials_preview") or []], limit=20)
        description = _clean(protocol.get("description"))
        text = " ".join(
            part
            for part in [
                _clean(protocol.get("title")),
                description,
                " ".join(steps),
                " ".join(materials),
            ]
            if part
        )

        if not steps and description:
            steps = _sentences(description)[:6]

        equipment = _dedupe(
            [term for term in EQUIPMENT_TERMS if term.lower() in text.lower()],
            limit=10,
        )
        conditions = _dedupe(CONDITION_PATTERN.findall(text), limit=12)
        warnings = _extract_matching_sentences(text, WARNING_TERMS, limit=8)
        validation_methods = _extract_matching_sentences(text, VALIDATION_TERMS, limit=8)

        missing_fields: list[str] = []
        if not steps:
            missing_fields.append("steps")
        if not materials:
            missing_fields.append("materials")
        if not equipment:
            missing_fields.append("equipment")
        if not validation_methods:
            missing_fields.append("validation_methods")

        extracted.append(
            ExtractedProtocolEvidence(
                source_id=source_id,
                title=_clean(protocol.get("title")) or "Untitled protocol",
                steps=steps,
                materials=materials,
                equipment=equipment,
                conditions=conditions,
                warnings=warnings,
                validation_methods=validation_methods,
                missing_fields=missing_fields,
            )
        )

    return extracted

