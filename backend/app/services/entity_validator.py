from __future__ import annotations

from typing import Any

from app.services.protocol_models import EntityValidation

ENTITY_SYNONYMS: dict[str, tuple[str, str]] = {
    "ipsc": ("cell_model", "induced pluripotent stem cell"),
    "hipsc": ("cell_model", "human induced pluripotent stem cell"),
    "induced pluripotent stem cell": ("cell_model", "induced pluripotent stem cell"),
    "hela": ("cell_line", "HeLa"),
    "c57bl/6": ("organism", "C57BL/6 mouse"),
    "trehalose": ("chemical", "trehalose"),
    "sucrose": ("chemical", "sucrose"),
    "dmso": ("chemical", "dimethyl sulfoxide"),
    "crp": ("protein", "C-reactive protein"),
    "c-reactive protein": ("protein", "C-reactive protein"),
}


def _candidate_entities(structured_hypothesis: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("model_system", "intervention", "control", "outcome", "assay", "mechanism"):
        value = structured_hypothesis.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    for keyword in structured_hypothesis.get("keywords") or []:
        if isinstance(keyword, str) and keyword.strip():
            values.append(keyword.strip())
    return values


def validate_entities(structured_hypothesis: dict[str, Any]) -> list[EntityValidation]:
    validations: list[EntityValidation] = []
    seen: set[str] = set()

    for entity in _candidate_entities(structured_hypothesis):
        lowered = entity.lower()
        match_key = next((key for key in ENTITY_SYNONYMS if key in lowered), None)
        if match_key:
            entity_type, normalized_name = ENTITY_SYNONYMS[match_key]
            status = "validated"
        else:
            entity_type = "scientific_term"
            normalized_name = entity
            status = "unverified"

        dedupe_key = f"{entity_type}:{normalized_name}".lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        validations.append(
            EntityValidation(
                entity=entity,
                type=entity_type,
                normalized_name=normalized_name,
                status=status,
            )
        )

    return validations[:12]

