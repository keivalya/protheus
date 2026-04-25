from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz, utils

CORE_FIELDS = ["model_system", "intervention", "outcome", "control", "assay"]

FIELD_LABELS = {
    "model_system": "model system",
    "intervention": "intervention",
    "outcome": "outcome",
    "control": "control",
    "assay": "assay/method",
}

FIELD_WEIGHTS = {
    "model_system": 0.22,
    "intervention": 0.30,
    "outcome": 0.30,
    "control": 0.08,
    "assay": 0.10,
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "into",
    "of",
    "on",
    "or",
    "protocol",
    "protocols",
    "the",
    "to",
    "with",
}


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _text_for_protocol(protocol: dict[str, Any]) -> str:
    chunks = [
        protocol.get("title"),
        protocol.get("description"),
        " ".join(protocol.get("steps_preview") or []),
        " ".join(protocol.get("materials_preview") or []),
    ]
    return " ".join(_clean(str(chunk)) for chunk in chunks if chunk)


def _tokens(value: str | None) -> list[str]:
    raw_tokens = re.findall(r"[a-zA-Z0-9/-]+", (value or "").lower())
    tokens = [token for token in raw_tokens if len(token) > 2 and token not in STOPWORDS]
    joined = (value or "").lower()
    if "induced pluripotent" in joined or "ipsc" in joined or "hipsc" in joined:
        tokens.append("ipsc")
    if "neuron" in joined or "neuronal" in joined or "neural" in joined or "ineuron" in joined:
        tokens.append("neuron")
    if "assembloid" in joined or "assembloids" in joined:
        tokens.append("assembloid")
    if "organoid" in joined or "organoids" in joined:
        tokens.append("organoid")
    if "spheroid" in joined or "spheroids" in joined:
        tokens.append("spheroid")
    if "cortical" in joined or "cortex" in joined:
        tokens.append("cortical")
    if "striatal" in joined or "striatum" in joined:
        tokens.append("striatal")
    if "forebrain" in joined:
        tokens.append("forebrain")
    if "fusion" in joined or "fused" in joined or "assemble" in joined or "assembly" in joined:
        tokens.extend(["fusion", "assembly"])
    if "connectivity" in joined or "circuit" in joined:
        tokens.extend(["connectivity", "circuit"])
    if "migration" in joined or "interneuron" in joined or "gabaergic" in joined:
        tokens.extend(["migration", "interneuron", "gabaergic"])
    if "c-reactive protein" in joined or "anti-crp" in joined:
        tokens.append("crp")
    if "post-thaw" in joined:
        tokens.extend(["post-thaw", "viability"])
    return tokens


def _normalize_bm25_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    if max_score <= 0:
        return [0.0 for _ in scores]
    return [min(1.0, score / max_score) for score in scores]


def _field_score(
    structured_hypothesis: dict[str, Any],
    protocol_text: str,
) -> tuple[float, list[str], list[str], dict[str, int]]:
    present_weight = 0.0
    weighted_score = 0.0
    matched_fields: list[str] = []
    missing_matches: list[str] = []
    field_scores: dict[str, int] = {}

    for field in CORE_FIELDS:
        field_value = structured_hypothesis.get(field)
        if not isinstance(field_value, str) or not field_value.strip():
            continue

        weight = FIELD_WEIGHTS[field]
        present_weight += weight
        field_tokens = set(_tokens(field_value))
        protocol_tokens = set(_tokens(protocol_text))
        overlap = field_tokens & protocol_tokens
        token_score = len(overlap) / len(field_tokens) if field_tokens else 0.0
        fuzzy_score = max(
            fuzz.WRatio(field_value, protocol_text[:600], processor=utils.default_process) / 100,
            fuzz.token_set_ratio(field_value, protocol_text[:600], processor=utils.default_process) / 100,
        )
        combined_score = 0.7 * token_score + 0.3 * fuzzy_score
        score = int(combined_score * 100)
        field_scores[field] = score

        threshold = 0.54
        if field == "model_system":
            threshold = 0.45
        if field in {"intervention", "outcome"}:
            threshold = 0.50

        critical_ok = True
        if "ipsc" in field_tokens and "ipsc" not in overlap:
            critical_ok = False
        if "assembloid" in field_tokens and "assembloid" not in overlap:
            critical_ok = False
        if "cortical" in field_tokens and "striatal" in field_tokens and not {"cortical", "striatal"} <= overlap:
            critical_ok = False
        if field in {"intervention", "outcome"} and "neuron" in field_tokens and "neuron" not in overlap:
            critical_ok = False

        if combined_score >= threshold and critical_ok:
            matched_fields.append(field)
            weighted_score += weight * min(1.0, combined_score)
        else:
            missing_matches.append(field)

    if present_weight <= 0:
        return 0.0, matched_fields, missing_matches, field_scores
    return weighted_score / present_weight, matched_fields, missing_matches, field_scores


def _completeness_score(protocol: dict[str, Any]) -> float:
    checks = [
        bool(protocol.get("title")),
        bool(protocol.get("description")),
        bool(protocol.get("steps_preview")),
        bool(protocol.get("materials_preview")),
    ]
    return sum(1 for check in checks if check) / len(checks)


def _metadata_quality_score(protocol: dict[str, Any]) -> float:
    checks = [
        bool(protocol.get("url")),
        bool(protocol.get("source")),
        bool(protocol.get("year")),
    ]
    return sum(1 for check in checks if check) / len(checks)


def _has_method_action_match(matched_fields: list[str]) -> bool:
    return bool({"intervention", "outcome", "assay"} & set(matched_fields))


def _has_model_conflict(structured_hypothesis: dict[str, Any], protocol_text: str) -> bool:
    model_system = str(structured_hypothesis.get("model_system") or "").lower()
    if not model_system:
        return False

    text = protocol_text.lower()
    if ("ipsc" in model_system or "induced pluripotent" in model_system) and (
        "ipsc" not in text and "induced pluripotent" not in text and "hipsc" not in text
    ):
        return True
    if "hela" in model_system and "hela" not in text:
        return True
    if "c57bl" in model_system and "c57bl" not in text:
        return True
    return False


def _human_no_animal_requested(structured_hypothesis: dict[str, Any]) -> bool:
    query_text = " ".join(
        str(value)
        for value in [
            structured_hypothesis.get("model_system"),
            structured_hypothesis.get("intervention"),
            structured_hypothesis.get("outcome"),
            " ".join(structured_hypothesis.get("keywords") or []),
        ]
        if value
    ).lower()
    return any(term in query_text for term in ["human-specific", "without animal", "no animal", "human induced"])


def _is_animal_only_protocol(protocol_text: str) -> bool:
    text = protocol_text.lower()
    animal_terms = ["rodent", "mouse", "mice", "rat", "zebrafish", "c57bl"]
    human_terms = ["human", "ipsc", "hipsc", "organoid", "spheroid", "assembloid"]
    return any(term in text for term in animal_terms) and not any(term in text for term in human_terms)


def _generic_only_match(
    matched_fields: list[str],
    structured_hypothesis: dict[str, Any],
    protocol_text: str,
) -> bool:
    if len(matched_fields) > 1:
        return False
    keyword_tokens: set[str] = set()
    for keyword in structured_hypothesis.get("keywords") or []:
        keyword_tokens.update(_tokens(keyword))
    overlap = keyword_tokens & set(_tokens(protocol_text))
    return len(overlap) <= 2


def _title_support_cap(
    score: float,
    protocol: dict[str, Any],
    structured_hypothesis: dict[str, Any],
) -> float:
    title = str(protocol.get("title") or "").lower()
    query_text = " ".join(
        str(value)
        for value in (
            structured_hypothesis.get("domain"),
            structured_hypothesis.get("model_system"),
            structured_hypothesis.get("intervention"),
            structured_hypothesis.get("outcome"),
            structured_hypothesis.get("assay"),
            " ".join(structured_hypothesis.get("keywords") or []),
        )
        if value
    ).lower()

    concept_terms: list[str] = []
    if "ipsc" in query_text or "induced pluripotent" in query_text or "neuron" in query_text:
        concept_terms.extend(["neuron", "neural", "neuronal", "ineuron", "ngn2", "ipsc", "hipsc", "differenti"])
    if any(term in query_text for term in ["assembloid", "organoid", "spheroid", "forebrain", "cortical", "striatal"]):
        concept_terms.extend(
            [
                "assembloid",
                "organoid",
                "spheroid",
                "forebrain",
                "cortical",
                "striatal",
                "brain",
                "circuit",
                "migration",
                "fusion",
                "fused",
                "assembly",
            ]
        )
    if "cryo" in query_text or "post-thaw" in query_text or "dmso" in query_text:
        concept_terms.extend(["cryo", "freez", "thaw", "dmso", "trehalose", "cryoprotect"])
    if "c-reactive" in query_text or "crp" in query_text or "biosensor" in query_text:
        concept_terms.extend(["crp", "c-reactive", "biosensor", "immuno", "antibody", "electrochemical"])
    if "intestinal" in query_text or "lactobacillus" in query_text or "permeability" in query_text:
        concept_terms.extend(["intestinal", "permeability", "fitc", "dextran", "lactobacillus", "probiotic"])

    capped_score = score
    if concept_terms and not any(term in title for term in concept_terms):
        capped_score = min(capped_score, 0.38)
    if (
        ("ipsc" in query_text or "induced pluripotent" in query_text)
        and any(term in query_text for term in ["neuron", "neural", "neuronal"])
        and any(term in query_text for term in ["differentiat", "derive", "derived", "generation"])
    ):
        neural_action_terms = [
            "differentiat",
            "derive",
            "derived",
            "neuron",
            "neural",
            "neuronal",
            "ineuron",
            "ngn2",
            "npc",
            "progenitor",
        ]
        if not any(term in title for term in neural_action_terms):
            capped_score = min(capped_score, 0.39)
    if any(term in query_text for term in ["cryo", "post-thaw", "dmso", "trehalose", "cryoprotect"]):
        cryo_action_terms = ["cryo", "freez", "freezing", "thaw", "dmso", "trehalose", "cryoprotect", "viability"]
        if not any(term in title for term in cryo_action_terms):
            capped_score = min(capped_score, 0.30)
    if any(term in query_text for term in ["assembloid", "organoid", "spheroid", "cortical", "striatal"]):
        assembloid_action_terms = [
            "assembloid",
            "organoid",
            "spheroid",
            "forebrain",
            "cortical",
            "striatal",
            "brain",
            "circuit",
            "migration",
            "fusion",
            "assembly",
        ]
        if not any(term in title for term in assembloid_action_terms):
            capped_score = min(capped_score, 0.34)
    return capped_score


def _apply_caps(
    score: float,
    protocol: dict[str, Any],
    protocol_text: str,
    structured_hypothesis: dict[str, Any],
    matched_fields: list[str],
) -> float:
    capped_score = score
    if not _has_method_action_match(matched_fields):
        capped_score = min(capped_score, 0.50)
    if _has_model_conflict(structured_hypothesis, protocol_text):
        capped_score = min(capped_score, 0.55)
    if not protocol.get("steps_preview"):
        capped_score = min(capped_score, 0.65)
    if _generic_only_match(matched_fields, structured_hypothesis, protocol_text):
        capped_score = min(capped_score, 0.40)
    if _human_no_animal_requested(structured_hypothesis) and _is_animal_only_protocol(protocol_text):
        capped_score = min(capped_score, 0.32)
    capped_score = _title_support_cap(capped_score, protocol, structured_hypothesis)
    return capped_score


def _match_tier(score: float) -> str:
    if score >= 0.72:
        return "strong_match"
    if score >= 0.42:
        return "related_protocol"
    return "weak_match"


def _match_reason(
    matched_fields: list[str],
    missing_matches: list[str],
    bm25_score: float,
) -> str:
    if matched_fields:
        labels = [FIELD_LABELS[field] for field in matched_fields]
        if len(labels) == 1:
            field_text = labels[0]
        else:
            field_text = f"{', '.join(labels[:-1])}, and {labels[-1]}"
        if bm25_score >= 0.55:
            return f"Matched {field_text}; BM25 also ranked the protocol text highly."
        return f"Matched {field_text}; keyword relevance was moderate."
    if missing_matches:
        return "Related terms appeared, but no structured hypothesis field matched strongly."
    return "No meaningful protocol match against the structured hypothesis."


def rank_protocols(
    protocols: list[dict[str, Any]],
    structured_hypothesis: dict[str, Any],
    protocol_search_queries: list[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not protocols:
        return []

    protocol_texts = [_text_for_protocol(protocol) for protocol in protocols]
    tokenized_corpus = [_tokens(text) for text in protocol_texts]
    bm25 = BM25Okapi(tokenized_corpus)
    query_text = " ".join(protocol_search_queries)
    bm25_scores = _normalize_bm25_scores([float(score) for score in bm25.get_scores(_tokens(query_text))])

    ranked: list[dict[str, Any]] = []
    for protocol, protocol_text, bm25_score in zip(protocols, protocol_texts, bm25_scores):
        field_match_score, matched_fields, missing_matches, _ = _field_score(
            structured_hypothesis,
            protocol_text,
        )
        completeness = _completeness_score(protocol)
        metadata_quality = _metadata_quality_score(protocol)
        raw_score = (
            0.45 * field_match_score
            + 0.35 * bm25_score
            + 0.15 * completeness
            + 0.05 * metadata_quality
        )
        final_score = _apply_caps(
            raw_score,
            protocol,
            protocol_text,
            structured_hypothesis,
            matched_fields,
        )
        final_score = round(min(1.0, max(0.0, final_score)), 2)
        ranked.append(
            {
                **protocol,
                "match_score": final_score,
                "match_tier": _match_tier(final_score),
                "match_reason": _match_reason(matched_fields, missing_matches, bm25_score),
                "matched_fields": matched_fields,
                "missing_matches": missing_matches,
            }
        )

    ranked.sort(key=lambda item: item.get("match_score", 0), reverse=True)
    return ranked[:limit]
