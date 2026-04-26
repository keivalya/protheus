from __future__ import annotations

import os
import re
from typing import Any

import httpx

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


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


def search_papers(search_queries: list[str], limit: int = 5) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_page = max(limit, 5)
    mailto = os.getenv("OPENALEX_MAILTO")

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
                dedupe_key = paper.get("doi") or _normalize_title(paper.get("title"))
                if not dedupe_key or dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                papers.append(paper)
    return papers

