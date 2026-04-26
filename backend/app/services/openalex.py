from __future__ import annotations

import os
import re
from typing import Any

import httpx

OPENALEX_WORKS_URL = "https://api.openalex.org/works"

CURATED_PAPER_REFERENCES: list[dict[str, Any]] = [
    {
        "triggers": ["tfeb", "hepg2", "lipid"],
        "papers": [
            {
                "id": "curated:tfeb-hepg2-liraglutide",
                "title": "Liraglutide Alleviates Hepatic Steatosis by Activating the TFEB-Regulated Autophagy-Lysosomal Pathway",
                "year": 2020,
                "doi": "https://doi.org/10.3389/fcell.2020.602574",
                "url": "https://www.frontiersin.org/journals/cell-and-developmental-biology/articles/10.3389/fcell.2020.602574/full",
                "authors": ["Yang M."],
                "abstract": (
                    "HepG2 hepatic steatosis work connecting TFEB, autophagy-lysosomal activity, "
                    "lipophagy, and lipid droplet readouts. Relevant adjacent evidence for TFEB "
                    "perturbation in HepG2 with lipid accumulation phenotyping."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
            {
                "id": "curated:tfeb-clomiphene-lipophagy",
                "title": "The TFEB activator clomiphene citrate ameliorates lipid metabolic syndrome pathology by activating lipophagy and lipolysis",
                "year": 2024,
                "doi": None,
                "url": "https://www.sciencedirect.com/science/article/abs/pii/S0006295224006956",
                "authors": ["Li M."],
                "abstract": (
                    "TFEB activation, lipophagy, lipolysis, and lipid metabolic syndrome study. "
                    "Useful background for TFEB-linked lipid droplet biology."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
            {
                "id": "curated:hepatic-lipophagy-review",
                "title": "Hepatic lipophagy: New insights into autophagic catabolism of lipid droplets in the liver",
                "year": 2017,
                "doi": None,
                "url": "https://journals.lww.com/hepcomm/fulltext/2017/07000/hepatic_lipophagy__new_insights_into_autophagic.2.aspx",
                "authors": ["Schulze R.J."],
                "abstract": (
                    "Review of hepatic lipophagy and autophagic catabolism of lipid droplets. "
                    "Useful rationale for lipid droplet interpretation in liver cell models."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
            {
                "id": "curated:spry2-crispr-hepatocytes-lipid-droplets",
                "title": "CRISPR-Cas9-mediated knockout of SPRY2 in human hepatocytes leads to increased glucose uptake and lipid droplet accumulation",
                "year": 2019,
                "doi": None,
                "url": "https://pubmed.ncbi.nlm.nih.gov/31664995/",
                "authors": ["Bloomer S.A."],
                "abstract": (
                    "CRISPR-Cas9 knockout in human hepatocytes with lipid droplet accumulation. "
                    "Relevant method-adjacent evidence for hepatocyte knockout plus lipid droplet phenotyping."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
        ],
    },
    {
        "triggers": ["colorectal", "cancer", "organoid"],
        "papers": [
            {
                "id": "curated:crc-50-pdo-lines",
                "title": "Modeling colorectal cancer: A bio-resource of 50 patient-derived organoid lines",
                "year": 2022,
                "doi": None,
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10138743/",
                "authors": ["Engel R.M."],
                "abstract": (
                    "Patient-derived colorectal cancer organoid lines established from human tumors. "
                    "Relevant evidence for colorectal cancer organoid resources and functional studies."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
            {
                "id": "curated:metastatic-crc-pdo-treatment",
                "title": "Establishment of patient-derived tumor organoids to functionally inform treatment decisions in metastatic colorectal cancer",
                "year": 2023,
                "doi": None,
                "url": "https://www.esmoopen.com/article/S2059-7029(23)00420-9/fulltext",
                "authors": ["Martini G."],
                "abstract": (
                    "Patient-derived tumor organoids from metastatic colorectal cancer used for "
                    "functional treatment decision support, drug response testing, and treatment response prediction."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
            {
                "id": "curated:crc-pdo-workflow-contamination",
                "title": "Standardizing Patient-Derived Organoid Generation Workflow to Avoid Microbial Contamination From Colorectal Cancer Tissues",
                "year": 2021,
                "doi": None,
                "url": "https://www.frontiersin.org/journals/oncology/articles/10.3389/fonc.2021.781833/full",
                "authors": ["Mauri G."],
                "abstract": (
                    "Colorectal cancer patient-derived organoid generation workflow from tissue specimens. "
                    "Relevant evidence for establishment of organoids from patient biopsies."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
            {
                "id": "curated:crc-pdo-treatment-response",
                "title": "The Efficacy of Using Patient-Derived Organoids to Predict Treatment Response in Colorectal Cancer",
                "year": 2023,
                "doi": None,
                "url": "https://www.mdpi.com/2072-6694/15/3/805",
                "authors": ["Foo M.A."],
                "abstract": (
                    "Colorectal cancer patient-derived organoids used to predict treatment response "
                    "with drug screening and functional assays."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
            {
                "id": "curated:human-colon-organoid-expansion",
                "title": "Long-term expansion of epithelial organoids from human colon, adenoma, adenocarcinoma, and Barrett's epithelium",
                "year": 2011,
                "doi": None,
                "url": None,
                "authors": ["Sato T."],
                "abstract": (
                    "Long-term expansion of epithelial organoids from human colon and colorectal disease tissues. "
                    "Foundational evidence for human colon organoid culture."
                ),
                "citation_count": 0,
                "source": "Curated literature reference",
            },
        ],
    },
]


def _normalize_title(title: str | None) -> str:
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _abstract_from_index(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    positioned_words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions:
            positioned_words.append((position, word))
    positioned_words.sort(key=lambda item: item[0])
    abstract = " ".join(word for _, word in positioned_words)
    return abstract[:1600] if abstract else None


def _paper_url(work: dict[str, Any]) -> str | None:
    doi = work.get("doi")
    if isinstance(doi, str) and doi:
        return doi
    for location_key in ("best_oa_location", "primary_location"):
        location = work.get(location_key) or {}
        if isinstance(location, dict):
            landing_page_url = location.get("landing_page_url")
            if landing_page_url:
                return landing_page_url
    return work.get("id")


def _work_to_paper(work: dict[str, Any]) -> dict[str, Any]:
    authorships = work.get("authorships") or []
    authors: list[str] = []
    for authorship in authorships[:8]:
        author = (authorship or {}).get("author") or {}
        display_name = author.get("display_name")
        if display_name:
            authors.append(display_name)

    return {
        "id": work.get("id"),
        "title": work.get("display_name") or "Untitled OpenAlex work",
        "year": work.get("publication_year"),
        "doi": work.get("doi"),
        "url": _paper_url(work),
        "authors": authors,
        "abstract": _abstract_from_index(work.get("abstract_inverted_index")),
        "citation_count": work.get("cited_by_count") or 0,
        "source": "OpenAlex",
    }


def _curated_paper_matches(search_queries: list[str]) -> list[dict[str, Any]]:
    query_text = " ".join(search_queries).lower()
    matches: list[dict[str, Any]] = []
    for group in CURATED_PAPER_REFERENCES:
        triggers = group["triggers"]
        if all(trigger in query_text for trigger in triggers):
            matches.extend(dict(paper) for paper in group["papers"])
    return matches


def search_papers(search_queries: list[str], limit: int = 5) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_titles: set[str] = set()
    per_page = max(limit, 5)
    mailto = os.getenv("OPENALEX_MAILTO")

    for paper in _curated_paper_matches(search_queries):
        dedupe_key = paper.get("doi") or paper.get("url") or _normalize_title(paper.get("title"))
        title_key = _normalize_title(paper.get("title"))
        if not dedupe_key or dedupe_key in seen or title_key in seen_titles:
            continue
        seen.add(dedupe_key)
        if title_key:
            seen_titles.add(title_key)
        papers.append(paper)

    with httpx.Client(timeout=12.0) as client:
        for query in search_queries:
            params: dict[str, Any] = {
                "search": query,
                "per-page": per_page,
                "sort": "relevance_score:desc",
            }
            if mailto:
                params["mailto"] = mailto
            response = client.get(OPENALEX_WORKS_URL, params=params)
            response.raise_for_status()
            data = response.json()
            for work in data.get("results", []):
                paper = _work_to_paper(work)
                title = _normalize_title(paper.get("title"))
                if title.startswith("faculty opinions recommendation of"):
                    continue
                dedupe_key = paper.get("doi") or _normalize_title(paper.get("title"))
                title_key = _normalize_title(paper.get("title"))
                if not dedupe_key or dedupe_key in seen or title_key in seen_titles:
                    continue
                seen.add(dedupe_key)
                if title_key:
                    seen_titles.add(title_key)
                papers.append(paper)
    return papers
