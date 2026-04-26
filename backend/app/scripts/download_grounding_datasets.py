from __future__ import annotations

import json
import re
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
GROUNDING_DIR = DATA_DIR / "grounding_corpus"
VALIDATION_DIR = DATA_DIR / "validation_corpus"
BIOPROBENCH_DIR = GROUNDING_DIR / "bioprobench"
BIOPROT_DIR = GROUNDING_DIR / "bioprot"
WLP_DIR = VALIDATION_DIR / "wet_lab_protocol_corpus"
CURATED_PATH = GROUNDING_DIR / "curated_protocol_examples.json"
MANIFEST_PATH = GROUNDING_DIR / "corpus_manifest.json"
CURATED_TARGET = 5000

BIOPROBENCH_API = "https://huggingface.co/api/datasets/BioProBench/BioProBench"
BIOPROBENCH_RAW = "https://huggingface.co/datasets/BioProBench/BioProBench/resolve/main"
BIOPROBENCH_FILES = [
    "GEN_test.json",
    "ORD_test.json",
    "ERR_test.json",
    "PQA_test.json",
]
BIOPROT_API = "https://api.github.com/repos/bioplanner/bioplanner/contents/bioprot"
WLP_ZIP_URL = "https://aclanthology.org/attachments/N18-2016.Datasets.zip"

KEYWORDS = [
    "cell",
    "ipsc",
    "hipsc",
    "neuron",
    "neuronal",
    "differentiation",
    "cryopreservation",
    "biosensor",
    "assay",
    "control",
    "validation",
    "immunostaining",
    "marker",
    "protein",
    "culture",
]


@dataclass
class SourceStats:
    source: str
    files_downloaded: int = 0
    raw_records_seen: int = 0
    curated_examples: int = 0
    bytes_on_disk: int = 0
    notes: list[str] | None = None


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return
    with urllib.request.urlopen(url, timeout=60) as response:
        target.write_bytes(response.read())


def _download_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _walk_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            strings.extend(_walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.extend(_walk_strings(item))
    return strings


def _records_from_json(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("data", "examples", "instances", "records", "protocols"):
            if isinstance(value.get(key), list):
                return value[key]
        return [value]
    return []


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _snippet_from_record(record: Any, max_chars: int = 520) -> str:
    strings = [_clean_text(text) for text in _walk_strings(record)]
    strings = [text for text in strings if len(text) >= 20]
    text = " ".join(strings)
    return text[:max_chars].strip()


def _score_text(text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in KEYWORDS if keyword in lowered)


def _domain_for_text(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["biosensor", "electrochemical", "crp", "c-reactive"]):
        return "diagnostics / biosensing"
    if any(term in lowered for term in ["cell", "ipsc", "neuron", "culture", "differentiation"]):
        return "cell_biology"
    return "biology_protocol"


def _experiment_type_for_text(text: str) -> str:
    lowered = text.lower()
    if "differentiation" in lowered and ("neuron" in lowered or "neural" in lowered):
        return "neuronal_differentiation"
    if "cryopreservation" in lowered or "post-thaw" in lowered:
        return "cryopreservation"
    if "biosensor" in lowered:
        return "biosensor_validation"
    if "assay" in lowered:
        return "assay"
    return "protocol_structure"


def _example(source: str, record_id: str, text: str, notes: list[str]) -> dict[str, Any]:
    return {
        "id": record_id,
        "source": source,
        "domain": _domain_for_text(text),
        "experiment_type": _experiment_type_for_text(text),
        "summary": text[:320],
        "structure_notes": notes,
    }


def download_bioprobench() -> SourceStats:
    BIOPROBENCH_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _download_json(BIOPROBENCH_API)
    (BIOPROBENCH_DIR / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for filename in BIOPROBENCH_FILES:
        _download(f"{BIOPROBENCH_RAW}/{filename}", BIOPROBENCH_DIR / filename)
    return SourceStats(
        source="BioProBench/BioProBench",
        files_downloaded=len(BIOPROBENCH_FILES) + 1,
        bytes_on_disk=_dir_size(BIOPROBENCH_DIR),
        notes=[
            f"Remote repository usedStorage bytes: {metadata.get('usedStorage')}",
            f"Remote downloads count: {metadata.get('downloads')}",
            "Downloaded small test/error/order/QA subset for hackathon grounding.",
        ],
    )


def download_bioprot() -> SourceStats:
    BIOPROT_DIR.mkdir(parents=True, exist_ok=True)
    listing = _download_json(BIOPROT_API)
    files = [item for item in listing if item.get("type") == "file" and item.get("name", "").endswith(".json")]
    for item in files:
        _download(item["download_url"], BIOPROT_DIR / item["name"])
    return SourceStats(
        source="bioplanner/bioplanner bioprot",
        files_downloaded=len(files),
        bytes_on_disk=_dir_size(BIOPROT_DIR),
        notes=["Downloaded BioProt JSON protocol files from GitHub."],
    )


def download_wet_lab_protocol_corpus() -> SourceStats:
    WLP_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = WLP_DIR / "wlp.zip"
    _download(WLP_ZIP_URL, zip_path)
    extract_dir = WLP_DIR / "extracted"
    if not extract_dir.exists():
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)
    return SourceStats(
        source="Wet Lab Protocol Corpus",
        files_downloaded=len([item for item in extract_dir.rglob("*") if item.is_file()]) + 1,
        bytes_on_disk=_dir_size(WLP_DIR),
        notes=["Downloaded ACL Anthology N18-2016 dataset zip and extracted it."],
    )


def _curate_from_json_dir(source: str, directory: Path, limit: int) -> tuple[list[dict[str, Any]], int]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    raw_records = 0
    for path in sorted(directory.glob("*.json")):
        if path.name == "metadata.json":
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records = _records_from_json(value)
        raw_records += len(records)
        for index, record in enumerate(records):
            snippet = _snippet_from_record(record)
            if not snippet:
                continue
            score = _score_text(snippet)
            if score <= 0 and len(candidates) >= limit:
                continue
            notes = [
                "Reference example for protocol structure, grounding or validation.",
                "Use only as retrieved context; do not treat as selected user evidence.",
            ]
            candidates.append((score, _example(source, f"{path.stem}:{index}", snippet, notes)))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [example for _, example in candidates[:limit]], raw_records


def _curate_from_wlp(limit: int) -> tuple[list[dict[str, Any]], int]:
    text_files = [
        path
        for path in (WLP_DIR / "extracted").rglob("*")
        if path.is_file() and path.suffix.lower() in {".txt", ".ann", ".tsv"}
    ]
    candidates: list[tuple[int, dict[str, Any]]] = []
    raw_records = 0
    for path in text_files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        snippet = _clean_text(text)[:520]
        if not snippet:
            continue
        raw_records += 1
        score = _score_text(snippet)
        notes = [
            "Wet Lab Protocol Corpus example for action/material/equipment extraction patterns.",
            "Use for validation structure checks rather than direct generation.",
        ]
        candidates.append((score, _example("Wet Lab Protocol Corpus", path.name, snippet, notes)))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [example for _, example in candidates[:limit]], raw_records


def curate_examples(stats: dict[str, SourceStats], limit: int = CURATED_TARGET) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []

    bioprobench_examples, bioprobench_records = _curate_from_json_dir(
        "BioProBench/BioProBench",
        BIOPROBENCH_DIR,
        3800,
    )
    stats["bioprobench"].raw_records_seen = bioprobench_records
    stats["bioprobench"].curated_examples = len(bioprobench_examples)
    examples.extend(bioprobench_examples)

    bioprot_examples, bioprot_records = _curate_from_json_dir(
        "BioPlanner BioProt",
        BIOPROT_DIR,
        100,
    )
    stats["bioprot"].raw_records_seen = bioprot_records
    stats["bioprot"].curated_examples = len(bioprot_examples)
    examples.extend(bioprot_examples)

    wlp_examples, wlp_records = _curate_from_wlp(1100)
    stats["wet_lab_protocol_corpus"].raw_records_seen = wlp_records
    stats["wet_lab_protocol_corpus"].curated_examples = len(wlp_examples)
    examples.extend(wlp_examples)

    examples = examples[:limit]
    CURATED_PATH.write_text(
        json.dumps({"examples": examples}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return examples


def write_manifest(stats: dict[str, SourceStats], curated_total: int) -> None:
    manifest = {
        "curated_examples_path": str(CURATED_PATH.relative_to(DATA_DIR)),
        "curated_examples_target": CURATED_TARGET,
        "curated_examples_total": curated_total,
        "sources": {
            key: {
                "source": value.source,
                "files_downloaded": value.files_downloaded,
                "raw_records_seen": value.raw_records_seen,
                "curated_examples": value.curated_examples,
                "bytes_on_disk": value.bytes_on_disk,
                "notes": value.notes or [],
            }
            for key, value in stats.items()
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    GROUNDING_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    stats = {
        "bioprobench": download_bioprobench(),
        "bioprot": download_bioprot(),
        "wet_lab_protocol_corpus": download_wet_lab_protocol_corpus(),
    }
    examples = curate_examples(stats)
    for value in stats.values():
        value.bytes_on_disk = _dir_size(
            {
                "BioProBench/BioProBench": BIOPROBENCH_DIR,
                "bioplanner/bioplanner bioprot": BIOPROT_DIR,
                "Wet Lab Protocol Corpus": WLP_DIR,
            }[value.source]
        )
    write_manifest(stats, len(examples))
    print(json.dumps(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")), indent=2))


if __name__ == "__main__":
    main()
