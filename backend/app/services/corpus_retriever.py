from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.protocol_models import CorpusExampleReference

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CURATED_PATH = DATA_DIR / "grounding_corpus" / "curated_protocol_examples.json"
MANIFEST_PATH = DATA_DIR / "grounding_corpus" / "corpus_manifest.json"
EMBEDDING_MANIFEST_PATH = DATA_DIR / "grounding_corpus" / "corpus_embedding_manifest.json"
DEFAULT_CHROMA_PATH = DATA_DIR / "chroma"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CORPUS_COLLECTION = "protocol_corpus_examples"


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9/-]+", text.lower())
        if len(token) > 2
        and token
        not in {
            "the",
            "and",
            "for",
            "with",
            "protocol",
            "protocols",
            "using",
            "from",
            "that",
        }
    }


def _query_text(structured_hypothesis: dict[str, Any]) -> str:
    parts = [
        structured_hypothesis.get("domain"),
        structured_hypothesis.get("model_system"),
        structured_hypothesis.get("intervention"),
        structured_hypothesis.get("outcome"),
        structured_hypothesis.get("assay"),
        structured_hypothesis.get("mechanism"),
        " ".join(structured_hypothesis.get("keywords") or []),
    ]
    return " ".join(str(part) for part in parts if part)


def _load_examples() -> list[dict[str, Any]]:
    try:
        payload = json.loads(CURATED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    examples = payload.get("examples")
    return examples if isinstance(examples, list) else []


def retrieve_corpus_examples(
    structured_hypothesis: dict[str, Any],
    limit: int = 5,
) -> list[CorpusExampleReference]:
    query = _query_text(structured_hypothesis)
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    examples = _load_examples()
    documents = [
        " ".join(
            str(part)
            for part in [
                example.get("domain"),
                example.get("experiment_type"),
                example.get("summary"),
                " ".join(example.get("structure_notes") or []),
            ]
            if part
        )
        for example in examples
    ]
    tokenized_docs = [list(_tokens(document)) for document in documents]

    try:
        from rank_bm25 import BM25Okapi

        bm25_scores = BM25Okapi(tokenized_docs).get_scores(list(query_tokens))
    except Exception:
        bm25_scores = [0.0 for _ in examples]

    try:
        from rapidfuzz import fuzz, utils
    except Exception:
        fuzz = None
        utils = None

    scored: list[tuple[float, dict[str, Any]]] = []
    max_bm25 = max(bm25_scores) if len(bm25_scores) else 0
    query_domain = structured_hypothesis.get("domain")
    query_assay_or_mechanism = structured_hypothesis.get("assay") or structured_hypothesis.get("mechanism")
    query_intervention = structured_hypothesis.get("intervention")

    for index, example in enumerate(examples):
        text = documents[index]
        text = " ".join(
            str(part)
            for part in [
                example.get("domain"),
                example.get("experiment_type"),
                example.get("summary"),
                " ".join(example.get("structure_notes") or []),
            ]
            if part
        )
        example_tokens = _tokens(text)
        if not example_tokens:
            continue
        normalized_bm25 = (float(bm25_scores[index]) / max_bm25) if max_bm25 > 0 else 0.0
        fuzzy_score = (
            fuzz.token_set_ratio(query, text, processor=utils.default_process) / 100
            if fuzz and utils and query
            else 0.0
        )
        metadata_score = 0.0
        if query_domain and example.get("domain") == query_domain:
            metadata_score += 1.0
        example_type = str(example.get("experiment_type") or "").lower()
        if query_assay_or_mechanism and str(query_assay_or_mechanism).lower() in example_type:
            metadata_score += 0.5
        if query_intervention and any(token in example_type for token in _tokens(str(query_intervention))):
            metadata_score += 0.5
        lexical_overlap = len(query_tokens & example_tokens) / max(len(query_tokens), 1)
        score = (
            0.45 * normalized_bm25
            + 0.25 * fuzzy_score
            + 0.20 * metadata_score
            + 0.10 * lexical_overlap
        )
        if score > 0:
            scored.append((score, example))

    scored.sort(key=lambda item: item[0], reverse=True)
    deterministic = [
        CorpusExampleReference(
            id=str(example.get("id") or index),
            source=str(example.get("source") or "local_corpus"),
            domain=example.get("domain"),
            experiment_type=example.get("experiment_type"),
            summary=str(example.get("summary") or ""),
            structure_notes=[str(item) for item in example.get("structure_notes") or []],
            score=round(score, 3),
            search_backend="bm25_metadata_rapidfuzz",
        )
        for index, (score, example) in enumerate(scored[:limit])
    ]
    if len(deterministic) >= limit and (not deterministic or deterministic[0].score >= 0.2):
        return deterministic[:limit]

    embedding_results = query_corpus_embedding_examples(
        structured_hypothesis,
        limit=limit - len(deterministic),
    )
    seen_ids = {example.id for example in deterministic}
    supplemental = [example for example in embedding_results if example.id not in seen_ids]
    return [*deterministic, *supplemental][:limit]


def _embedding_query_text(structured_hypothesis: dict[str, Any]) -> str:
    return _query_text(structured_hypothesis)


def query_corpus_embedding_examples(
    structured_hypothesis: dict[str, Any],
    limit: int = 5,
) -> list[CorpusExampleReference]:
    if limit <= 0:
        return []
    query = _embedding_query_text(structured_hypothesis)
    if not query:
        return []

    try:
        import os

        import chromadb
        from sentence_transformers import SentenceTransformer
    except Exception:
        return []

    try:
        chroma_path = Path(os.getenv("AI_SCIENTIST_CHROMA_PATH") or DEFAULT_CHROMA_PATH)
        client = chromadb.PersistentClient(path=str(chroma_path))
        collection = client.get_collection(CORPUS_COLLECTION)
        model_name = os.getenv("AI_SCIENTIST_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        model = SentenceTransformer(model_name)
        embedding = model.encode([query], normalize_embeddings=True)
        result = collection.query(
            query_embeddings=embedding.tolist(),
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    examples: list[CorpusExampleReference] = []
    for index, example_id in enumerate(ids):
        metadata = metadatas[index] or {}
        notes_value = metadata.get("structure_notes") or "[]"
        try:
            structure_notes = json.loads(notes_value)
        except json.JSONDecodeError:
            structure_notes = []
        distance = distances[index] if index < len(distances) else None
        score = max(0.0, 1.0 - float(distance)) if distance is not None else 0.0
        examples.append(
            CorpusExampleReference(
                id=str(example_id),
                source=str(metadata.get("source") or "local_corpus"),
                domain=metadata.get("domain") or None,
                experiment_type=metadata.get("experiment_type") or None,
                summary=str(metadata.get("summary") or documents[index] or ""),
                structure_notes=[str(item) for item in structure_notes],
                score=round(score, 3),
                search_backend="chroma_embeddings",
            )
        )
    return examples


def corpus_manifest() -> dict[str, Any]:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {
            "curated_examples_path": str(CURATED_PATH.relative_to(DATA_DIR)),
            "curated_examples_total": len(_load_examples()),
            "sources": {},
        }
    try:
        manifest["embedding_index"] = json.loads(
            EMBEDDING_MANIFEST_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        manifest["embedding_index"] = {
            "indexed_examples": 0,
            "status": "not_built",
        }
    return manifest
