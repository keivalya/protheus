from __future__ import annotations

import re
from typing import Any

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "cell",
    "cells",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "protocol",
    "protocols",
    "standard",
    "the",
    "to",
    "with",
    "will",
}

FIELD_WEIGHTS = {
    "intervention": 0.34,
    "model_system": 0.16,
    "outcome": 0.28,
    "control": 0.12,
    "assay": 0.10,
}

FIELD_LABELS = {
    "intervention": "intervention",
    "model_system": "model system",
    "outcome": "outcome",
    "control": "control",
    "assay": "assay/method",
}


def _tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    raw_tokens = re.findall(r"[a-zA-Z0-9/-]+", text.lower())
    tokens = {token for token in raw_tokens if len(token) > 2 and token not in STOPWORDS}
    joined = text.lower()
    if "c-reactive protein" in joined:
        tokens.add("crp")
    if "anti-crp" in joined:
        tokens.add("crp")
        tokens.add("antibody")
    if "post-thaw" in joined:
        tokens.add("post-thaw")
        tokens.add("viability")
    if "ipsc" in joined or "induced pluripotent" in joined:
        tokens.add("ipsc")
    if "neuron" in joined or "neuronal" in joined or "neural" in joined or "ineuron" in joined:
        tokens.add("neuron")
    return tokens


def _candidate_text(item: dict[str, Any]) -> str:
    chunks = [
        item.get("title"),
        item.get("abstract"),
        item.get("description"),
        " ".join(item.get("authors") or []),
        " ".join(item.get("steps_preview") or []),
        " ".join(item.get("materials_preview") or []),
    ]
    return " ".join(str(chunk) for chunk in chunks if chunk)


def _has_field_match(field: str, field_tokens: set[str], overlap: set[str]) -> bool:
    if not overlap:
        return False
    if "crp" in field_tokens and "crp" not in overlap:
        return False
    if field == "outcome" and "neuron" in field_tokens and "neuron" not in overlap:
        return False
    if field == "model_system":
        return True
    if len(field_tokens) >= 3:
        return len(overlap) >= 2
    return True


def _score_item(item: dict[str, Any], structured_hypothesis: dict[str, Any]) -> tuple[float, list[str], str]:
    text_tokens = _tokens(_candidate_text(item))
    matched_fields: list[str] = []
    present_weight = 0.0
    matched_weight = 0.0

    for field, weight in FIELD_WEIGHTS.items():
        field_value = structured_hypothesis.get(field)
        field_tokens = _tokens(field_value if isinstance(field_value, str) else None)
        if not field_tokens:
            continue
        present_weight += weight
        overlap = field_tokens & text_tokens
        if _has_field_match(field, field_tokens, overlap):
            overlap_ratio = len(overlap) / len(field_tokens)
            matched_weight += weight * min(1.0, 0.35 + overlap_ratio)
            matched_fields.append(field)

    base_score = matched_weight / present_weight if present_weight else 0.0

    keyword_tokens: set[str] = set()
    for keyword in structured_hypothesis.get("keywords") or []:
        keyword_tokens.update(_tokens(keyword))
    keyword_overlap = keyword_tokens & text_tokens
    keyword_bonus = min(0.14, len(keyword_overlap) * 0.018)

    score = min(1.0, base_score * 0.88 + keyword_bonus)
    reason = _match_reason(matched_fields, len(keyword_overlap))
    return round(score, 2), matched_fields, reason


def _match_reason(matched_fields: list[str], keyword_overlap_count: int) -> str:
    if matched_fields:
        labels = [FIELD_LABELS[field] for field in matched_fields]
        if len(labels) == 1:
            return f"Matched the hypothesis {labels[0]} with limited supporting keyword overlap."
        return f"Matched the hypothesis {', '.join(labels[:-1])}, and {labels[-1]}."
    if keyword_overlap_count:
        return f"Matched {keyword_overlap_count} hypothesis keyword{'s' if keyword_overlap_count != 1 else ''}, but no core field matched clearly."
    return "No meaningful keyword overlap with the structured hypothesis."


def _apply_protocol_title_penalty(
    item: dict[str, Any],
    score: float,
    structured_hypothesis: dict[str, Any],
) -> float:
    if item.get("source") != "protocols.io":
        return score

    outcome_tokens = _tokens(structured_hypothesis.get("outcome"))
    intervention_tokens = _tokens(structured_hypothesis.get("intervention"))
    if "neuron" not in outcome_tokens and "neuron" not in intervention_tokens:
        return score

    title = str(item.get("title") or "").lower()
    title_supports_query = any(
        needle in title
        for needle in (
            "neuron",
            "neural",
            "neuronal",
            "ipsc",
            "hipsc",
            "differentiation",
            "differentiat",
            "ngn2",
            "lmns",
        )
    )
    return score if title_supports_query else score * 0.55


def rank_results(
    items: list[dict[str, Any]],
    structured_hypothesis: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in items:
        score, matched_fields, reason = _score_item(item, structured_hypothesis)
        score = round(_apply_protocol_title_penalty(item, score, structured_hypothesis), 2)
        ranked.append(
            {
                **item,
                "match_score": score,
                "match_reason": reason,
                "matched_fields": matched_fields,
            }
        )
    ranked.sort(key=lambda item: item.get("match_score", 0), reverse=True)
    return ranked[:limit]
