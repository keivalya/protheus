from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

FIELD_NAMES = [
    "domain",
    "model_system",
    "intervention",
    "control",
    "outcome",
    "effect_size",
    "assay",
    "mechanism",
    "keywords",
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "will",
    "with",
}


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip(" .,:;")
    return value or None


def _regex(pattern: str, query: str) -> str | None:
    match = re.search(pattern, query, flags=re.IGNORECASE)
    if not match:
        return None
    return _clean(match.group(1))


def _detect_domain(lower_query: str) -> str | None:
    rules = [
        (("ipsc", "neuron", "differenti"), "stem cell biology / neuronal differentiation"),
        (("cryoprotectant", "cryopreservation", "post-thaw", "freezing medium"), "cell cryopreservation"),
        (("biosensor", "electrochemical", "c-reactive protein", "crp"), "diagnostics / biosensing"),
        (("lactobacillus", "intestinal permeability", "c57bl/6", "microbiome"), "microbiome / gut barrier"),
        (("antibody", "immunosensor", "whole blood"), "immunoassay diagnostics"),
        (("cell", "viability", "hela"), "cell biology"),
    ]
    for needles, domain in rules:
        if any(needle in lower_query for needle in needles):
            return domain
    return None


def _detect_model_system(query: str) -> str | None:
    patterns = [
        r"\b(hiPSCs?|human induced pluripotent stem cells?)\b",
        r"\b(iPSCs?|induced pluripotent stem cells?)\b",
        r"\b(HeLa cells?)\b",
        r"\b(C57BL/6 mice)\b",
        r"\b(whole blood)\b",
        r"\b(mouse|mice|rat|rats|zebrafish|yeast|E\.?\s*coli)\b",
        r"\b([A-Z][A-Za-z0-9/-]+ cells?)\b",
    ]
    for pattern in patterns:
        value = _regex(pattern, query)
        if value:
            return value
    return None


def _detect_intervention(query: str) -> str | None:
    lower_query = query.lower()
    if (
        ("ipsc" in lower_query or "induced pluripotent" in lower_query)
        and "neuron" in lower_query
        and re.search(r"\b(derive|differentiate|differentiated|differentiation)\b", lower_query)
    ):
        return "differentiate iPSCs into neurons"

    replacing = re.search(
        r"replacing\s+(.{2,80}?)\s+with\s+(.{2,80}?)(?:\s+as\b|\s+will\b|\s+to\b|,|\.|$)",
        query,
        flags=re.IGNORECASE,
    )
    if replacing:
        old_value = _clean(replacing.group(1))
        new_value = _clean(replacing.group(2))
        if old_value and new_value:
            return f"{new_value} replacing {old_value}"

    supplementing = re.search(
        r"supplementing\s+(.{2,80}?)\s+with\s+(.{2,120}?)(?:\s+for\s+\d|\s+will\b|,|\.|$)",
        query,
        flags=re.IGNORECASE,
    )
    if supplementing:
        intervention = _clean(supplementing.group(2))
        if intervention:
            return intervention

    functionalized = _regex(r"functionalized\s+with\s+(.{2,120}?)(?:\s+will\b|,|\.|$)", query)
    if functionalized:
        return functionalized

    treated = _regex(r"(?:treated|exposed|dosed)\s+with\s+(.{2,120}?)(?:\s+will\b|,|\.|$)", query)
    if treated:
        return treated

    return None


def _detect_control(query: str) -> str | None:
    compared = _regex(r"compared\s+to\s+(.{2,120}?)(?:\.|$)", query)
    if compared:
        return compared
    versus = _regex(r"\bversus\s+(.{2,80}?)(?:\.|$)", query)
    if versus:
        return versus
    if re.search(r"\bcontrols?\b", query, flags=re.IGNORECASE):
        return "controls"
    return None


def _detect_outcome(query: str) -> str | None:
    lower_query = query.lower()
    if (
        ("ipsc" in lower_query or "induced pluripotent" in lower_query)
        and "neuron" in lower_query
        and re.search(r"\b(derive|differentiate|differentiated|differentiation)\b", lower_query)
    ):
        return "differentiated neurons"

    outcome = _regex(
        r"\bwill\s+(increase|decrease|reduce|improve|detect|inhibit|induce)\s+(.{2,140}?)(?:\s+by\s+at\s+least|\s+by\b|\s+below\b|\s+within\b|\s+compared\b|\.|$)",
        query,
    )
    if outcome:
        # _regex returns only the first capturing group for this pattern, so handle it explicitly.
        match = re.search(
            r"\bwill\s+(increase|decrease|reduce|improve|detect|inhibit|induce)\s+(.{2,140}?)(?:\s+by\s+at\s+least|\s+by\b|\s+below\b|\s+within\b|\s+compared\b|\.|$)",
            query,
            flags=re.IGNORECASE,
        )
        if match:
            return _clean(f"{match.group(1)} {match.group(2)}")
    return None


def _detect_effect_size(query: str) -> str | None:
    patterns = [
        r"((?:by\s+)?at least\s+\d+(?:\.\d+)?\s*(?:percentage points?|percent|%))",
        r"(below\s+\d+(?:\.\d+)?\s*(?:mg/L|ng/mL|pg/mL|uM|µM|mM)(?:\s+within\s+\d+\s+\w+)?)",
        r"(within\s+\d+\s+\w+)",
        r"(\d+(?:\.\d+)?\s*(?:percentage points?|percent|%))",
    ]
    matches: list[str] = []
    for pattern in patterns:
        value = _regex(pattern, query)
        if value and value.lower() not in {m.lower() for m in matches}:
            matches.append(value)
    return "; ".join(matches) if matches else None


def _detect_assay(lower_query: str) -> str | None:
    rules = [
        (("post-thaw viability", "viability"), "post-thaw viability assay"),
        (("electrochemical", "biosensor"), "electrochemical biosensor assay"),
        (("c-reactive protein", "crp", "anti-crp"), "CRP immunoassay"),
        (("intestinal permeability", "fitc-dextran"), "intestinal permeability assay"),
    ]
    for needles, assay in rules:
        if any(needle in lower_query for needle in needles):
            return assay
    return None


def _detect_mechanism(lower_query: str) -> str | None:
    rules = [
        (("ipsc", "neuron", "differenti"), "neuronal differentiation"),
        (("cryoprotectant", "trehalose", "post-thaw"), "cryoprotection"),
        (("anti-crp", "antibodies", "antibody"), "antibody-antigen binding"),
        (("lactobacillus", "intestinal permeability", "microbiome"), "microbiome-mediated gut barrier modulation"),
    ]
    for needles, mechanism in rules:
        if any(needle in lower_query for needle in needles):
            return mechanism
    return None


def _extract_keywords(query: str, structured: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("model_system", "intervention", "control", "outcome", "assay", "mechanism"):
        value = structured.get(key)
        if isinstance(value, str):
            candidates.append(value)

    known_terms = [
        "trehalose",
        "sucrose",
        "cryoprotectant",
        "cryopreservation",
        "post-thaw viability",
        "DMSO",
        "HeLa",
        "anti-CRP antibodies",
        "C-reactive protein",
        "CRP",
        "whole blood",
        "electrochemical biosensor",
        "paper-based",
        "Lactobacillus rhamnosus GG",
        "C57BL/6",
        "intestinal permeability",
        "FITC-dextran",
    ]
    lower_query = query.lower()
    for term in known_terms:
        if term.lower() in lower_query:
            candidates.append(term)

    words = re.findall(r"[A-Za-z][A-Za-z0-9/-]{3,}", query)
    for word in words:
        if word.lower() not in STOPWORDS:
            candidates.append(word)

    deduped: OrderedDict[str, None] = OrderedDict()
    for candidate in candidates:
        cleaned = _clean(candidate)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in deduped:
            deduped[cleaned] = None
    return list(deduped.keys())[:14]


def _trim_model_from_outcome(outcome: str | None, model_system: str | None) -> str | None:
    if not outcome or not model_system:
        return outcome
    model_pattern = re.escape(model_system)
    outcome = re.sub(rf"\s+(?:of|in)\s+{model_pattern}\b", "", outcome, flags=re.IGNORECASE)
    return _clean(outcome)


def structure_hypothesis_rule_based(query: str) -> dict[str, Any]:
    lower_query = query.lower()
    structured: dict[str, Any] = {
        "domain": _detect_domain(lower_query),
        "model_system": _detect_model_system(query),
        "intervention": _detect_intervention(query),
        "control": _detect_control(query),
        "outcome": _detect_outcome(query),
        "effect_size": _detect_effect_size(query),
        "assay": _detect_assay(lower_query),
        "mechanism": _detect_mechanism(lower_query),
        "keywords": [],
    }
    structured["outcome"] = _trim_model_from_outcome(
        structured.get("outcome"),
        structured.get("model_system"),
    )
    structured["keywords"] = _extract_keywords(query, structured)
    return {field: structured.get(field) for field in FIELD_NAMES}


def structure_hypothesis(query: str) -> dict[str, Any]:
    try:
        from app.services.openai_hypothesis import structure_hypothesis_with_openai

        structured = structure_hypothesis_with_openai(query)
        if structured:
            rule_based = structure_hypothesis_rule_based(query)
            for field in FIELD_NAMES:
                if field == "keywords":
                    combined_keywords = list(structured.get("keywords") or [])
                    for keyword in rule_based.get("keywords") or []:
                        if keyword.lower() not in {item.lower() for item in combined_keywords}:
                            combined_keywords.append(keyword)
                    structured["keywords"] = combined_keywords[:14]
                elif structured.get(field) is None and rule_based.get(field) is not None:
                    structured[field] = rule_based[field]
            structured["outcome"] = _trim_model_from_outcome(
                structured.get("outcome"),
                structured.get("model_system"),
            )
            return structured
    except Exception:
        pass
    return structure_hypothesis_rule_based(query)


def _join_query_parts(*parts: str | None) -> str | None:
    cleaned = [_clean(part) for part in parts if _clean(part)]
    if not cleaned:
        return None
    return " ".join(cleaned)


def _searchable_intervention(intervention: str | None) -> str | None:
    if not intervention:
        return None
    replace_match = re.match(
        r"replace\s+(.+?)\s+with\s+(.+?)(?:\s+in\b|\s+as\b|$)",
        intervention,
        flags=re.IGNORECASE,
    )
    if replace_match:
        return _clean(f"{replace_match.group(2)} {replace_match.group(1)}")
    replacing_match = re.match(r"(.+?)\s+replacing\s+(.+)", intervention, flags=re.IGNORECASE)
    if replacing_match:
        return _clean(f"{replacing_match.group(1)} {replacing_match.group(2)}")
    return intervention


def generate_search_queries(structured_hypothesis: dict[str, Any], query: str) -> list[str]:
    keywords = structured_hypothesis.get("keywords") or []
    keyword_text = " ".join(keywords[:6]) if isinstance(keywords, list) else ""
    searchable_intervention = _searchable_intervention(structured_hypothesis.get("intervention"))

    exact_style = _join_query_parts(
        structured_hypothesis.get("model_system"),
        searchable_intervention,
        structured_hypothesis.get("outcome"),
        structured_hypothesis.get("control"),
    )
    broader_method = _join_query_parts(
        searchable_intervention,
        structured_hypothesis.get("model_system"),
        structured_hypothesis.get("assay"),
    )
    protocol_style = _join_query_parts(
        searchable_intervention,
        structured_hypothesis.get("model_system"),
        structured_hypothesis.get("domain"),
        "protocol",
    )

    ordered = [exact_style, broader_method, protocol_style, keyword_text, query]
    seen: set[str] = set()
    search_queries: list[str] = []
    for item in ordered:
        cleaned = _clean(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            search_queries.append(cleaned)
            seen.add(key)
        if len(search_queries) == 3:
            break
    return search_queries or [query]
