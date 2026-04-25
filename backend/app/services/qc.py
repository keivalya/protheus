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
            "explanation": "No close match was found because the searched sources returned no usable results. This is not evidence that the experiment has never been done.",
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

    if strong_core_match:
        return {
            "novelty_signal": "exact match found",
            "confidence": round(min(0.95, 0.78 + max_score * 0.17), 2),
            "explanation": "A top searched result matched the model system, intervention, control, and outcome. Treat this as a prior-work flag that should be checked manually.",
        }

    if max_score >= 0.24:
        return {
            "novelty_signal": "similar work exists",
            "confidence": round(min(0.86, 0.48 + max_score * 0.42), 2),
            "explanation": "Related work exists, but no exact match was found for this precise model, intervention, control, and outcome in the searched sources.",
        }

    return {
        "novelty_signal": "not found",
        "confidence": round(max(0.42, 0.58 - max_score * 0.3), 2),
        "explanation": "No close match was found in the searched sources. This is not evidence that the experiment has never been done.",
    }
