from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
GROUNDING_DIR = DATA_DIR / "grounding_corpus"
CURATED_PATH = GROUNDING_DIR / "curated_protocol_examples.json"
EMBEDDING_MANIFEST_PATH = GROUNDING_DIR / "corpus_embedding_manifest.json"
DEFAULT_CHROMA_PATH = DATA_DIR / "chroma"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CORPUS_COLLECTION = "protocol_corpus_examples"


def _load_examples(limit: int | None = None) -> tuple[list[dict[str, Any]], int]:
    payload = json.loads(CURATED_PATH.read_text(encoding="utf-8"))
    examples = payload.get("examples")
    if not isinstance(examples, list):
        examples = []
    total = len(examples)
    if limit is not None:
        examples = examples[:limit]
    return examples, total


def _document(example: dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in [
            example.get("domain"),
            example.get("experiment_type"),
            example.get("summary"),
            " ".join(example.get("structure_notes") or []),
        ]
        if part
    )


def _metadata(example: dict[str, Any]) -> dict[str, str]:
    return {
        "source": str(example.get("source") or "local_corpus"),
        "domain": str(example.get("domain") or ""),
        "experiment_type": str(example.get("experiment_type") or ""),
        "original_id": str(example.get("id") or ""),
        "summary": str(example.get("summary") or ""),
        "structure_notes": json.dumps(example.get("structure_notes") or []),
    }


def _batched(values: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [values[index : index + batch_size] for index in range(0, len(values), batch_size)]


def build_index(limit: int | None, batch_size: int, reset: bool) -> dict[str, Any]:
    import chromadb
    from sentence_transformers import SentenceTransformer

    examples, curated_total = _load_examples(limit)
    chroma_path = Path(os.getenv("AI_SCIENTIST_CHROMA_PATH") or DEFAULT_CHROMA_PATH)
    model_name = os.getenv("AI_SCIENTIST_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    chroma_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(chroma_path))
    if reset:
        try:
            client.delete_collection(CORPUS_COLLECTION)
        except Exception:
            pass
    collection = client.get_or_create_collection(
        name=CORPUS_COLLECTION,
        metadata={
            "description": "Curated biological protocol examples for structural retrieval",
            "hnsw:space": "cosine",
        },
    )
    model = SentenceTransformer(model_name)

    indexed = 0
    for batch in _batched(examples, max(batch_size, 1)):
        documents = [_document(example) for example in batch]
        ids = [str(example.get("id") or f"corpus:{indexed + offset}") for offset, example in enumerate(batch)]
        metadatas = [_metadata(example) for example in batch]
        embeddings = model.encode(documents, normalize_embeddings=True, show_progress_bar=False)
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings,
            metadatas=metadatas,
        )
        indexed += len(batch)
        print(f"indexed {indexed}/{len(examples)}")

    manifest = {
        "status": "built",
        "collection": CORPUS_COLLECTION,
        "indexed_examples": indexed,
        "curated_examples_total": curated_total,
        "embedding_model": model_name,
        "chroma_path": str(chroma_path.relative_to(DATA_DIR) if chroma_path.is_relative_to(DATA_DIR) else chroma_path),
        "source_examples_path": str(CURATED_PATH.relative_to(DATA_DIR)),
    }
    EMBEDDING_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the optional Chroma embedding index for curated protocol examples.")
    parser.add_argument("--limit", type=int, default=None, help="Optional max examples to index.")
    parser.add_argument("--batch-size", type=int, default=128, help="Embedding/indexing batch size.")
    parser.add_argument("--no-reset", action="store_true", help="Do not delete the existing collection first.")
    args = parser.parse_args()
    manifest = build_index(limit=args.limit, batch_size=args.batch_size, reset=not args.no_reset)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
