from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.services.protocol_db import mark_feedback_memory_indexed, search_feedback_memories_sqlite
from app.services.protocol_models import FeedbackMemoryReference

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_CHROMA_PATH = DATA_DIR / "chroma"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _query_text(structured_hypothesis: dict[str, Any]) -> str:
    keywords = structured_hypothesis.get("keywords") or []
    parts = [
        structured_hypothesis.get("domain"),
        structured_hypothesis.get("model_system"),
        structured_hypothesis.get("intervention"),
        structured_hypothesis.get("outcome"),
        structured_hypothesis.get("assay"),
        structured_hypothesis.get("mechanism"),
        *keywords[:8],
        "protocol validation workflow controls",
    ]
    return " ".join(str(part) for part in parts if part)


class FeedbackMemoryIndex:
    def __init__(self) -> None:
        self._client = None
        self._collection = None
        self._model = None
        self.disabled_reason: str | None = None

    def _ensure(self) -> bool:
        if self._collection is not None and self._model is not None:
            return True
        if self.disabled_reason:
            return False

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            self.disabled_reason = f"ChromaDB/SentenceTransformers unavailable: {exc}"
            return False

        try:
            chroma_path = Path(os.getenv("AI_SCIENTIST_CHROMA_PATH") or DEFAULT_CHROMA_PATH)
            chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(chroma_path))
            self._collection = self._client.get_or_create_collection(
                name="researcher_feedback_memory",
                metadata={"description": "Reusable researcher feedback for protocol drafts"},
            )
            model_name = os.getenv("AI_SCIENTIST_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
            self._model = SentenceTransformer(model_name)
        except Exception as exc:
            self.disabled_reason = f"Feedback memory index unavailable: {exc}"
            return False
        return True

    def _embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings

    def add_memory(self, memory: FeedbackMemoryReference) -> bool:
        if not self._ensure():
            return False
        metadata = {
            "domain": memory.domain or "",
            "experiment_type": memory.experiment_type or "",
            "model_system": memory.model_system or "",
            "intervention": memory.intervention or "",
            "outcome": memory.outcome or "",
            "section": memory.section or "",
            "accepted": True,
        }
        try:
            self._collection.upsert(
                ids=[memory.id],
                documents=[memory.memory_text],
                embeddings=self._embed([memory.memory_text]),
                metadatas=[metadata],
            )
            mark_feedback_memory_indexed(memory.id)
            return True
        except Exception as exc:
            self.disabled_reason = f"Feedback memory index write failed: {exc}"
            return False

    def query(self, structured_hypothesis: dict[str, Any], limit: int = 5) -> list[FeedbackMemoryReference]:
        query = _query_text(structured_hypothesis)
        if not query or not self._ensure():
            return []

        try:
            result = self._collection.query(
                query_embeddings=self._embed([query]),
                n_results=limit,
                where={"accepted": True},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            self.disabled_reason = f"Feedback memory index query failed: {exc}"
            return []

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        memories: list[FeedbackMemoryReference] = []
        for index, memory_id in enumerate(ids):
            metadata = metadatas[index] or {}
            memories.append(
                FeedbackMemoryReference(
                    id=memory_id,
                    memory_text=documents[index] or "",
                    domain=metadata.get("domain") or None,
                    experiment_type=metadata.get("experiment_type") or None,
                    model_system=metadata.get("model_system") or None,
                    intervention=metadata.get("intervention") or None,
                    outcome=metadata.get("outcome") or None,
                    section=metadata.get("section") or None,
                    distance=distances[index] if index < len(distances) else None,
                    search_backend="chroma",
                )
            )
        return memories


feedback_memory_index = FeedbackMemoryIndex()


def index_feedback_memories(memories: list[FeedbackMemoryReference]) -> int:
    indexed = 0
    for memory in memories:
        if feedback_memory_index.add_memory(memory):
            indexed += 1
    return indexed


def retrieve_feedback_memories(
    structured_hypothesis: dict[str, Any],
    limit: int = 5,
) -> list[FeedbackMemoryReference]:
    deterministic_results = search_feedback_memories_sqlite(structured_hypothesis, limit=limit)
    if len(deterministic_results) >= limit:
        return deterministic_results[:limit]

    chroma_results = feedback_memory_index.query(
        structured_hypothesis,
        limit=limit - len(deterministic_results),
    )
    seen_ids = {memory.id for memory in deterministic_results}
    supplemental = [memory for memory in chroma_results if memory.id not in seen_ids]
    return [*deterministic_results, *supplemental][:limit]
