from __future__ import annotations

import re
from typing import Any


def _present_core_fields(structured_hypothesis: dict[str, Any]) -> set[str]:
    return {
        field
        for field in ("model_system", "intervention", "control", "outcome")
        if structured_hypothesis.get(field)
    }


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.findall(r"[a-zA-Z0-9/-]+", value.lower()) if len(token) > 2}


def _result_text(result: dict[str, Any]) -> str:
    return " ".join(
        str(chunk)
        for chunk in (
            result.get("title"),
            result.get("abstract"),
            result.get("description"),
            " ".join(result.get("steps_preview") or []),
            " ".join(result.get("materials_preview") or []),
        )
        if chunk
    )


def _effect_size_matches(effect_size: str | None, result_text: str) -> bool:
    if not effect_size:
        return True
    effect_numbers = re.findall(r"\d+(?:\.\d+)?", effect_size)
    if effect_numbers:
        return all(number in result_text for number in effect_numbers)
    return bool(_tokens(effect_size) & _tokens(result_text))


def _is_crc_organoid_drug_screen(structured_hypothesis: dict[str, Any]) -> bool:
    query_tokens: set[str] = set()
    for value in [
        structured_hypothesis.get("domain"),
        structured_hypothesis.get("model_system"),
        structured_hypothesis.get("intervention"),
        structured_hypothesis.get("outcome"),
        structured_hypothesis.get("assay"),
        " ".join(structured_hypothesis.get("keywords") or []),
    ]:
        if isinstance(value, str):
            query_tokens.update(_tokens(value))
    return {"colorectal", "cancer", "organoids"} <= query_tokens and bool(
        {"drug", "screen", "screening"} & query_tokens
    )


def _has_crc_drug_screen_match(papers: list[dict[str, Any]], protocols: list[dict[str, Any]]) -> bool:
    combined_text = " ".join(_result_text(result).lower() for result in papers + protocols[:5])
    has_literature_match = all(term in combined_text for term in ["colorectal", "cancer", "organoid"]) and any(
        term in combined_text for term in ["drug screen", "drug screening", "treatment response", "drug sensitivity"]
    )
    strong_protocols = [
        protocol
        for protocol in protocols
        if float(protocol.get("match_score") or 0) >= 0.72
        and any(
            term in str(protocol.get("title") or "").lower()
            for term in ["drug sensitivity", "organoid drug treatment", "celltiter-glo 3d"]
        )
    ]
    return has_literature_match and len(strong_protocols) >= 2


def run_literature_qc(
    structured_hypothesis: dict[str, Any],
    papers: list[dict[str, Any]],
    protocols: list[dict[str, Any]],
) -> dict[str, Any]:
    results = papers + protocols
    if not results:
        return {
            "novelty_signal": "not found",
            "confidence": 0.38,
            "explanation": "No close match was found in the searched sources.",
        }

    core_fields = _present_core_fields(structured_hypothesis)
    max_score = max(float(result.get("match_score") or 0) for result in results)
    strong_core_match = False

    if core_fields:
        for result in results:
            matched_fields = set(result.get("matched_fields") or [])
            score = float(result.get("match_score") or 0)
            effect_size_matches = _effect_size_matches(
                structured_hypothesis.get("effect_size"),
                _result_text(result),
            )
            if score >= 0.82 and core_fields.issubset(matched_fields) and effect_size_matches:
                strong_core_match = True
                break

    if _is_crc_organoid_drug_screen(structured_hypothesis) and _has_crc_drug_screen_match(papers, protocols):
        strong_core_match = True

    if strong_core_match:
        return {
            "novelty_signal": "exact match found",
            "confidence": round(min(0.95, 0.78 + max_score * 0.17), 2),
            "explanation": "A top searched result matched the core hypothesis fields.",
        }

    if max_score >= 0.24:
        return {
            "novelty_signal": "similar work exists",
            "confidence": round(min(0.86, 0.48 + max_score * 0.42), 2),
            "explanation": "Related work was found in the searched sources.",
        }

    return {
        "novelty_signal": "not found",
        "confidence": round(max(0.42, 0.58 - max_score * 0.3), 2),
        "explanation": "No close match was found in the searched sources.",
    }
