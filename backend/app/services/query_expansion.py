from __future__ import annotations

import os
import re
import warnings
from functools import lru_cache
from typing import Any

try:
    from rapidfuzz import fuzz, process, utils
except Exception:  # pragma: no cover - optional fallback for incomplete local installs
    fuzz = None
    process = None
    utils = None

NORMALIZATION_PATTERNS = [
    (r"\bdifferenciated\b", "differentiated"),
    (r"\bdifferntiation\b", "differentiation"),
    (r"\bdifferentation\b", "differentiation"),
    (r"\bipscs\b", "iPSCs"),
    (r"\bipsc\b", "iPSC"),
    (r"\bhipscs\b", "hiPSCs"),
    (r"\bhipsc\b", "hiPSC"),
    (r"\bips cells\b", "induced pluripotent stem cells"),
    (r"\bbrain spheroids\b", "brain spheroids"),
    (r"\bcrp\b", "C-reactive protein"),
    (r"\bfitc dextran\b", "FITC-dextran"),
    (r"\bc57bl6\b", "C57BL/6"),
]

BIOMEDICAL_CONCEPTS = [
    {
        "canonical": "TFEB HepG2 lipid droplet CRISPR knockout",
        "aliases": [
            "TFEB HepG2 lipid droplets",
            "CRISPR knockout of TFEB in HepG2",
            "HepG2 lipid droplet BODIPY",
            "TFEB lipophagy HepG2",
            "fatty acid loading lipid droplets HepG2",
            "Cas9 RNP adherent cells",
        ],
        "protocol_queries": [
            "CRISPR Editing of Immortalized Cells with RNPs using Lipofection",
            "Transfection of Cas9 RNP into adherent cells using Lipofectamine RNAiMAX",
            "Limiting Dilution Clonal Expansion",
            "Lipid droplet visualisation in cultured cells using BODIPY 493/503 stain",
            "HepG2 lipid droplet BODIPY protocol",
            "TFEB CRISPR knockout HepG2 lipid droplet protocol",
        ],
        "paper_queries": [
            "Liraglutide Alleviates Hepatic Steatosis by Activating the TFEB-Regulated Autophagy-Lysosomal Pathway",
            "TFEB HepG2 lipid droplets siRNA lipophagy",
            "TFEB activator clomiphene citrate lipophagy lipolysis",
            "Hepatic lipophagy autophagic catabolism lipid droplets liver",
            "CRISPR-Cas9 knockout human hepatocytes lipid droplet accumulation",
        ],
    },
    {
        "canonical": "patient-derived colorectal cancer organoid drug screen",
        "aliases": [
            "established colorectal cancer organoids from patient biopsies drug screen",
            "colorectal cancer organoids from patient biopsies drug screen",
            "established colorectal cancer organoids patient biopsies",
            "colorectal cancer organoids patient biopsies drug screen",
            "patient-derived CRC organoids drug screening",
            "patient-derived tumor organoids metastatic colorectal cancer",
            "colorectal cancer patient-derived organoid generation workflow",
            "CellTiter-Glo 3D organoid drug treatment",
        ],
        "protocol_queries": [
            "Cell Viability Protocol using CellTiter-Glo 3D",
            "Organoid Drug Treatment",
            "Drug Sensitivity Assays of Human Cancer Organoid Cultures",
            "patient-derived colorectal cancer organoid drug screening protocol",
            "colorectal cancer organoids patient biopsies drug screen",
        ],
        "paper_queries": [
            "Modeling colorectal cancer: A bio-resource of 50 patient-derived organoid lines",
            "Establishment of patient-derived tumor organoids to functionally inform treatment decisions in metastatic colorectal cancer",
            "Standardizing Patient-Derived Organoid Generation Workflow to Avoid Microbial Contamination From Colorectal Cancer Tissues",
            "The Efficacy of Using Patient-Derived Organoids to Predict Treatment Response in Colorectal Cancer",
            "Long-term expansion of epithelial organoids from human colon adenoma adenocarcinoma Barrett's epithelium",
        ],
    },
    {
        "canonical": "iPSC neuron differentiation",
        "aliases": [
            "derive neurons from iPSC",
            "differentiate iPSCs into neurons",
            "differentiated neurons from iPSCs",
            "iPSC-derived neurons",
            "hiPSC neurons",
            "human induced pluripotent stem cell neurons",
            "neuronal differentiation from pluripotent stem cells",
            "neural induction iPSC",
            "NGN2 neurons",
        ],
        "protocol_queries": [
            "iPSC neuron differentiation",
            "hiPSC neuron differentiation",
            "induced pluripotent stem cell neuronal differentiation",
            "iPSC-derived neurons",
            "neural differentiation iPSC",
            "NGN2 neuron induction",
            "midbrain neuron differentiation iPSC",
        ],
        "paper_queries": [
            "iPSC-derived neuron differentiation protocol",
            "human induced pluripotent stem cells neuronal differentiation",
            "NGN2 induced neurons iPSC differentiation",
        ],
    },
    {
        "canonical": "hiPSC cortical striatal assembloid",
        "aliases": [
            "human cortical and striatal organoids",
            "cortical striatal organoid fusion",
            "cortical and striatal assembloid",
            "brain assembloids",
            "forebrain spheroids",
            "human forebrain spheroid assembly",
            "inter-regional connectivity",
            "interregional connectivity",
            "neuronal migration defects",
            "GABAergic neuron migration",
            "engineering brain assembloids",
        ],
        "protocol_queries": [
            "Engineering brain assembloids to interrogate human neural circuits",
            "human cortical striatal organoid fusion assembloid protocol",
            "hiPSC cortical striatal assembloid protocol",
            "human forebrain spheroid assembly protocol",
            "cortical striatal brain assembloids inter-regional connectivity",
            "organoid fusion neuronal migration assembloid",
            "GABAergic neuron migration forebrain spheroids protocol",
        ],
        "paper_queries": [
            "Assembly of functionally integrated human forebrain spheroids",
            "human forebrain spheroids cortical striatal organoid fusion",
            "GABAergic neuron migration human forebrain spheroids Nature 2017",
            "human cortical striatal assembloids inter-regional connectivity",
        ],
    },
    {
        "canonical": "cell cryopreservation",
        "aliases": [
            "cryopreservation",
            "cryoprotectant",
            "post-thaw viability",
            "freezing medium",
            "DMSO freezing protocol",
            "trehalose cryopreservation",
        ],
        "protocol_queries": [
            "cell cryopreservation",
            "mammalian cell cryopreservation",
            "post-thaw viability assay",
            "DMSO cryopreservation",
            "trehalose cryopreservation",
        ],
        "paper_queries": [
            "trehalose DMSO cryopreservation post-thaw viability",
            "mammalian cell cryoprotectant post-thaw viability",
        ],
    },
    {
        "canonical": "CRP biosensor",
        "aliases": [
            "C-reactive protein biosensor",
            "CRP immunosensor",
            "anti-CRP antibody",
            "paper-based electrochemical biosensor",
            "whole blood CRP detection",
        ],
        "protocol_queries": [
            "C-reactive protein immunoassay",
            "CRP biosensor",
            "electrochemical biosensor",
            "whole blood biosensor",
            "anti-CRP antibody immunoassay",
        ],
        "paper_queries": [
            "paper-based electrochemical biosensor C-reactive protein whole blood",
            "anti-CRP antibody immunosensor detection limit whole blood",
        ],
    },
    {
        "canonical": "gut permeability probiotic",
        "aliases": [
            "intestinal permeability",
            "FITC-dextran permeability",
            "Lactobacillus rhamnosus GG",
            "C57BL/6 mice gut barrier",
            "probiotic gut permeability",
        ],
        "protocol_queries": [
            "FITC-dextran intestinal permeability",
            "mouse intestinal permeability assay",
            "Lactobacillus rhamnosus GG mouse",
            "C57BL/6 gut permeability",
        ],
        "paper_queries": [
            "Lactobacillus rhamnosus GG intestinal permeability C57BL/6 mice",
            "probiotic FITC-dextran gut barrier mice",
        ],
    },
]


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"\s+", " ", value).strip(" .,:;")
    return value or None


def _dedupe(values: list[str], limit: int = 10) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = _clean(value)
        if not cleaned:
            continue
        if len(cleaned) > 120 or len(cleaned.split()) > 14:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        deduped.append(cleaned)
        seen.add(key)
        if len(deduped) >= limit:
            break
    return deduped


def _join_query_parts(*parts: str | None) -> str | None:
    cleaned = [_clean(part) for part in parts if _clean(part)]
    return " ".join(cleaned) if cleaned else None


def normalize_scientific_query(query: str) -> str:
    normalized = query.strip()
    for pattern, replacement in NORMALIZATION_PATTERNS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


@lru_cache(maxsize=1)
def _load_scispacy_model() -> Any | None:
    model_name = os.getenv("SCISPACY_MODEL", "en_core_sci_sm")
    try:
        import scispacy  # noqa: F401
        import spacy

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            return spacy.load(model_name)
    except Exception:
        return None


def extract_scientific_entities(query: str) -> list[str]:
    nlp = _load_scispacy_model()
    if nlp is None:
        return []
    doc = nlp(query)
    entities = [
        entity.text.strip()
        for entity in doc.ents
        if len(entity.text.strip()) >= 3 and not entity.text.strip().isdigit()
    ]
    return _dedupe(entities, limit=10)


def _matched_concepts(query: str, structured_hypothesis: dict[str, Any]) -> list[dict[str, Any]]:
    haystack_parts = [
        query,
        structured_hypothesis.get("domain"),
        structured_hypothesis.get("model_system"),
        structured_hypothesis.get("intervention"),
        structured_hypothesis.get("outcome"),
        structured_hypothesis.get("assay"),
        " ".join(structured_hypothesis.get("keywords") or []),
    ]
    haystack = " ".join(str(part) for part in haystack_parts if part)
    haystack_lower = haystack.lower()
    haystack_tokens = {
        token
        for token in re.findall(r"[a-zA-Z0-9/-]+", haystack_lower)
        if len(token) > 2
        and token
        not in {
            "anyone",
            "done",
            "looked",
            "cells",
            "cell",
            "protocol",
            "protocols",
            "using",
            "from",
            "with",
            "and",
            "the",
        }
    }

    matched: list[dict[str, Any]] = []
    for concept in BIOMEDICAL_CONCEPTS:
        aliases = [concept["canonical"], *concept["aliases"]]
        canonical = concept["canonical"]
        required_concept_match = False
        if canonical == "patient-derived colorectal cancer organoid drug screen":
            required_concept_match = {"colorectal", "cancer", "organoid"} <= haystack_tokens and bool(
                {"drug", "screen", "screening"} & haystack_tokens
            )
        if canonical == "TFEB HepG2 lipid droplet CRISPR knockout":
            required_concept_match = {"tfeb", "hepg2"} <= haystack_tokens and bool(
                {"lipid", "droplets", "droplet"} & haystack_tokens
            )
        substring_match = any(alias.lower() in haystack_lower for alias in aliases)
        fuzzy_match = False
        if process and fuzz and utils:
            relevant_aliases = [
                alias
                for alias in aliases
                if len(
                    {
                        token
                        for token in re.findall(r"[a-zA-Z0-9/-]+", alias.lower())
                        if len(token) > 2
                    }
                    & haystack_tokens
                )
                >= 2
            ]
            if not relevant_aliases and not substring_match:
                continue
            if relevant_aliases:
                match = process.extractOne(
                    haystack,
                    relevant_aliases,
                    scorer=fuzz.WRatio,
                    processor=utils.default_process,
                )
                fuzzy_match = bool(match and match[1] >= 82)
        if substring_match or fuzzy_match or required_concept_match:
            matched.append(concept)
    return matched


def generate_protocol_search_queries(
    query: str,
    structured_hypothesis: dict[str, Any],
) -> list[str]:
    normalized_query = normalize_scientific_query(query)
    entities = extract_scientific_entities(normalized_query)
    candidates: list[str] = []

    for concept in _matched_concepts(normalized_query, structured_hypothesis):
        candidates.extend(concept["protocol_queries"])

    candidates.extend(
        [
            _join_query_parts(structured_hypothesis.get("model_system"), structured_hypothesis.get("outcome")),
            _join_query_parts(structured_hypothesis.get("intervention"), structured_hypothesis.get("outcome")),
            _join_query_parts(structured_hypothesis.get("assay"), structured_hypothesis.get("model_system")),
            *entities[:4],
            normalized_query,
        ]
    )
    return _dedupe(candidates, limit=10)


def generate_paper_search_queries(
    query: str,
    structured_hypothesis: dict[str, Any],
) -> list[str]:
    normalized_query = normalize_scientific_query(query)
    entities = extract_scientific_entities(normalized_query)
    candidates: list[str] = []

    for concept in _matched_concepts(normalized_query, structured_hypothesis):
        candidates.extend(concept["paper_queries"])

    candidates.extend(
        [
            _join_query_parts(
                structured_hypothesis.get("model_system"),
                structured_hypothesis.get("intervention"),
                structured_hypothesis.get("outcome"),
            ),
            _join_query_parts(structured_hypothesis.get("intervention"), structured_hypothesis.get("assay")),
            _join_query_parts(*entities[:4]),
            normalized_query,
        ]
    )
    return _dedupe(candidates, limit=6)


def build_semantic_weight_profile(query: str, structured_hypothesis: dict[str, Any]) -> dict[str, Any]:
    normalized_query = normalize_scientific_query(query)
    haystack = " ".join(
        str(part)
        for part in [
            normalized_query,
            structured_hypothesis.get("model_system"),
            structured_hypothesis.get("intervention"),
            structured_hypothesis.get("outcome"),
            structured_hypothesis.get("assay"),
            " ".join(structured_hypothesis.get("keywords") or []),
        ]
        if part
    ).lower()

    def present(values: list[str]) -> list[str]:
        return [value for value in values if value.lower() in haystack]

    negative_filters: list[str] = []
    if any(term in haystack for term in ["without animal", "no animal", "human-specific"]):
        negative_filters.extend(["rodent-only", "mouse-only", "rat-only"])

    return {
        "primary_entities": {
            "weight": 0.40,
            "tokens": present(["hiPSC", "iPSC", "organoid", "organoids", "assembloid", "assembloids"]),
        },
        "regional_specificity": {
            "weight": 0.25,
            "tokens": present(["cortical", "striatal", "forebrain", "dorsal", "ventral"]),
        },
        "functional_intent": {
            "weight": 0.25,
            "tokens": present(
                [
                    "fusion",
                    "fused",
                    "assembly",
                    "inter-regional connectivity",
                    "interregional connectivity",
                    "circuit assembly",
                    "neuronal migration",
                    "migration defects",
                ]
            ),
        },
        "negative_filters": {
            "weight": 0.10,
            "tokens": negative_filters,
        },
        "retrieval_note": "Selected protocols remain the grounding source; this profile is for retrieval/ranking diagnostics.",
    }


def build_query_debug(query: str, structured_hypothesis: dict[str, Any]) -> dict[str, Any]:
    normalized_query = normalize_scientific_query(query)
    return {
        "normalized_query": normalized_query,
        "scientific_entities": extract_scientific_entities(normalized_query),
        "protocol_search_queries": generate_protocol_search_queries(normalized_query, structured_hypothesis),
        "paper_search_queries": generate_paper_search_queries(normalized_query, structured_hypothesis),
        "semantic_weight_profile": build_semantic_weight_profile(normalized_query, structured_hypothesis),
        "scispacy_model": os.getenv("SCISPACY_MODEL", "en_core_sci_sm"),
        "scispacy_available": _load_scispacy_model() is not None,
        "rapidfuzz_available": bool(process and fuzz and utils),
    }
