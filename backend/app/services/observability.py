from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LOCAL_TRACE_PATH = DATA_DIR / "observability" / "protocol_traces.jsonl"


class NoopObservation:
    def __init__(self) -> None:
        self.input_data: dict[str, Any] | None = None
        self.metadata: dict[str, Any] | None = None
        self.output_data: dict[str, Any] | None = None

    def update(self, **_: Any) -> None:
        if "input" in _:
            self.input_data = _.get("input")
        if "metadata" in _:
            self.metadata = _.get("metadata")
        if "output" in _:
            self.output_data = _.get("output")
        return None


@dataclass
class ObservabilityStatus:
    provider: str = "local_jsonl"
    installed: bool = True
    configured: bool = True
    enabled: bool = True
    trace_path: str | None = None
    reason: str | None = None


def _enabled_by_env() -> bool:
    value = os.getenv("LOCAL_PROTOCOL_TRACING_ENABLED", "true").lower()
    return value not in {"0", "false", "no", "off"}


def _write_local_trace(record: dict[str, Any]) -> None:
    if not _enabled_by_env():
        return
    try:
        import json

        LOCAL_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOCAL_TRACE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        return


@contextmanager
def trace_span(
    name: str,
    *,
    as_type: str = "span",
    input_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    session_id: str | None = None,
    trace_name: str | None = None,
    tags: list[str] | None = None,
    version: str = "custom-protocol-module",
) -> Iterator[Any]:
    started_at = datetime.now(timezone.utc)
    observation = NoopObservation()
    observation.input_data = input_data
    observation.metadata = metadata
    error: Exception | None = None
    try:
        yield observation
    except Exception as exc:
        error = exc
        raise
    finally:
        finished_at = datetime.now(timezone.utc)
        status = "error" if error else "ok"
        record = {
            "name": name,
            "type": as_type,
            "session_id": session_id,
            "trace_name": trace_name,
            "tags": tags or [],
            "version": version,
            "status": status,
            "input": input_data,
            "metadata": observation.metadata or metadata or {},
            "output": observation.output_data or output_data,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": round((finished_at - started_at).total_seconds() * 1000, 3),
        }
        if error:
            record["error"] = str(error)
        _write_local_trace(
            record
        )


def flush_observability() -> None:
    return None


def observability_status() -> dict[str, Any]:
    if not _enabled_by_env():
        status = ObservabilityStatus(
            enabled=False,
            trace_path=str(LOCAL_TRACE_PATH.relative_to(DATA_DIR)),
            reason="LOCAL_PROTOCOL_TRACING_ENABLED is disabled.",
        )
    else:
        status = ObservabilityStatus(
            trace_path=str(LOCAL_TRACE_PATH.relative_to(DATA_DIR)),
            reason=None,
        )
    return status.__dict__
