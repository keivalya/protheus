from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from app.services.protocol_models import (
    CustomProtocolDraft,
    FeedbackMemoryReference,
    ProtocolFeedbackCreate,
    ProtocolFeedbackResponse,
    ProtocolSessionCreate,
    ProtocolSessionDetail,
    ProtocolValidationReport,
    ProtocolVerifierReport,
    ProtocolVersionResponse,
    TransparencyEventResponse,
    TransparencyStatus,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DB_PATH = DATA_DIR / "ai_scientist.sqlite3"


def _db_path() -> Path:
    configured = os.getenv("AI_SCIENTIST_DB_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(_db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def init_protocol_tables() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS protocol_sessions (
              id TEXT PRIMARY KEY,
              original_query TEXT NOT NULL,
              structured_hypothesis_json TEXT NOT NULL,
              selected_papers_json TEXT,
              selected_protocols_json TEXT,
              lab_context_json TEXT,
              status TEXT DEFAULT 'draft',
              accepted_version_id TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS protocol_versions (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              version_number INTEGER NOT NULL,
              parent_version_id TEXT,
              protocol_json TEXT NOT NULL,
              verifier_report_json TEXT,
              validation_report_json TEXT,
              change_summary TEXT,
              status TEXT DEFAULT 'draft',
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(session_id) REFERENCES protocol_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS protocol_feedback (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              version_id TEXT NOT NULL,
              section TEXT NOT NULL,
              feedback_type TEXT NOT NULL,
              original_text TEXT,
              feedback_text TEXT,
              reason TEXT,
              severity TEXT,
              reusable BOOLEAN DEFAULT false,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(session_id) REFERENCES protocol_sessions(id),
              FOREIGN KEY(version_id) REFERENCES protocol_versions(id)
            );

            CREATE TABLE IF NOT EXISTS feedback_memory (
              id TEXT PRIMARY KEY,
              memory_text TEXT NOT NULL,
              domain TEXT,
              experiment_type TEXT,
              model_system TEXT,
              intervention TEXT,
              outcome TEXT,
              section TEXT,
              source_feedback_id TEXT UNIQUE,
              accepted BOOLEAN DEFAULT true,
              chroma_indexed BOOLEAN DEFAULT false,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(source_feedback_id) REFERENCES protocol_feedback(id)
            );

            CREATE TABLE IF NOT EXISTS transparency_events (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              version_id TEXT,
              stage TEXT NOT NULL,
              status TEXT NOT NULL,
              user_message TEXT NOT NULL,
              details_json TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(session_id) REFERENCES protocol_sessions(id),
              FOREIGN KEY(version_id) REFERENCES protocol_versions(id)
            );

            CREATE TABLE IF NOT EXISTS operational_plans (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL UNIQUE,
              version_id TEXT NOT NULL,
              plan_json TEXT NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(session_id) REFERENCES protocol_sessions(id),
              FOREIGN KEY(version_id) REFERENCES protocol_versions(id)
            );
            """
        )
        version_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(protocol_versions)").fetchall()
        }
        if "verifier_report_json" not in version_columns:
            connection.execute(
                "ALTER TABLE protocol_versions ADD COLUMN verifier_report_json TEXT"
            )
        if "validation_report_json" not in version_columns:
            connection.execute(
                "ALTER TABLE protocol_versions ADD COLUMN validation_report_json TEXT"
            )


def create_protocol_session(payload: ProtocolSessionCreate) -> str:
    session_id = str(uuid.uuid4())
    lab_context = payload.lab_context.model_dump() if payload.lab_context else None
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO protocol_sessions (
                id,
                original_query,
                structured_hypothesis_json,
                selected_papers_json,
                selected_protocols_json,
                lab_context_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload.original_query.strip(),
                _json_dumps(payload.structured_hypothesis),
                _json_dumps(payload.selected_papers),
                _json_dumps(payload.selected_protocols),
                _json_dumps(lab_context) if lab_context is not None else None,
            ),
        )
    return session_id


def _session_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "original_query": row["original_query"],
        "structured_hypothesis": _json_loads(row["structured_hypothesis_json"], {}),
        "selected_papers": _json_loads(row["selected_papers_json"], []),
        "selected_protocols": _json_loads(row["selected_protocols_json"], []),
        "lab_context": _json_loads(row["lab_context_json"], None),
        "status": row["status"],
        "accepted_version_id": row["accepted_version_id"],
        "created_at": row["created_at"],
    }


def get_protocol_session_record(session_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM protocol_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return _session_from_row(row) if row else None


def _version_from_row(row: sqlite3.Row) -> ProtocolVersionResponse:
    protocol_payload = _json_loads(row["protocol_json"], {})
    row_keys = set(row.keys())
    verifier_report_payload = (
        _json_loads(row["verifier_report_json"], None)
        if "verifier_report_json" in row_keys
        else None
    )
    validation_report_payload = (
        _json_loads(row["validation_report_json"], None)
        if "validation_report_json" in row_keys
        else None
    )
    return ProtocolVersionResponse(
        id=row["id"],
        session_id=row["session_id"],
        version_number=row["version_number"],
        parent_version_id=row["parent_version_id"],
        protocol=CustomProtocolDraft.model_validate(protocol_payload),
        verifier_report=(
            ProtocolVerifierReport.model_validate(verifier_report_payload)
            if verifier_report_payload
            else None
        ),
        validation_report=(
            ProtocolValidationReport.model_validate(validation_report_payload)
            if validation_report_payload
            else None
        ),
        change_summary=row["change_summary"],
        status=row["status"],
        created_at=row["created_at"],
    )


def create_protocol_version(
    session_id: str,
    protocol: CustomProtocolDraft,
    parent_version_id: str | None = None,
    verifier_report: ProtocolVerifierReport | None = None,
    validation_report: ProtocolValidationReport | None = None,
    change_summary: str | None = None,
    status: str = "draft",
) -> ProtocolVersionResponse:
    version_id = str(uuid.uuid4())
    with _connect() as connection:
        current = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS latest FROM protocol_versions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        version_number = int(current["latest"]) + 1
        connection.execute(
            """
            INSERT INTO protocol_versions (
                id,
                session_id,
                version_number,
                parent_version_id,
                protocol_json,
                verifier_report_json,
                validation_report_json,
                change_summary,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                session_id,
                version_number,
                parent_version_id,
                _json_dumps(protocol.model_dump()),
                _json_dumps(verifier_report.model_dump()) if verifier_report else None,
                _json_dumps(validation_report.model_dump()) if validation_report else None,
                change_summary,
                status,
            ),
        )
        row = connection.execute(
            "SELECT * FROM protocol_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
    return _version_from_row(row)


def list_protocol_versions(session_id: str) -> list[ProtocolVersionResponse]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM protocol_versions WHERE session_id = ? ORDER BY version_number",
            (session_id,),
        ).fetchall()
    return [_version_from_row(row) for row in rows]


def get_protocol_version(version_id: str) -> ProtocolVersionResponse | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM protocol_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
    return _version_from_row(row) if row else None


def get_latest_protocol_version(session_id: str) -> ProtocolVersionResponse | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM protocol_versions
            WHERE session_id = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    return _version_from_row(row) if row else None


def _feedback_from_row(row: sqlite3.Row) -> ProtocolFeedbackResponse:
    return ProtocolFeedbackResponse(
        id=row["id"],
        session_id=row["session_id"],
        version_id=row["version_id"],
        section=row["section"],
        feedback_type=row["feedback_type"],
        original_text=row["original_text"],
        feedback_text=row["feedback_text"],
        reason=row["reason"],
        severity=row["severity"],
        reusable=bool(row["reusable"]),
        created_at=row["created_at"],
    )


def create_protocol_feedback(session_id: str, payload: ProtocolFeedbackCreate) -> ProtocolFeedbackResponse:
    feedback_id = str(uuid.uuid4())
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO protocol_feedback (
                id,
                session_id,
                version_id,
                section,
                feedback_type,
                original_text,
                feedback_text,
                reason,
                severity,
                reusable
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                session_id,
                payload.version_id,
                payload.section,
                payload.feedback_type,
                payload.original_text,
                payload.feedback_text,
                payload.reason,
                payload.severity,
                int(payload.reusable),
            ),
        )
        row = connection.execute(
            "SELECT * FROM protocol_feedback WHERE id = ?",
            (feedback_id,),
        ).fetchone()
    return _feedback_from_row(row)


def list_protocol_feedback(
    session_id: str,
    version_id: str | None = None,
    reusable_only: bool = False,
) -> list[ProtocolFeedbackResponse]:
    query = "SELECT * FROM protocol_feedback WHERE session_id = ?"
    params: list[Any] = [session_id]
    if version_id:
        query += " AND version_id = ?"
        params.append(version_id)
    if reusable_only:
        query += " AND reusable = 1"
    query += " ORDER BY created_at, id"

    with _connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_feedback_from_row(row) for row in rows]


def get_protocol_session_detail(session_id: str) -> ProtocolSessionDetail | None:
    session = get_protocol_session_record(session_id)
    if not session:
        return None
    return ProtocolSessionDetail(
        **session,
        versions=list_protocol_versions(session_id),
        feedback=list_protocol_feedback(session_id),
    )


def _transparency_event_from_row(row: sqlite3.Row) -> TransparencyEventResponse:
    return TransparencyEventResponse(
        id=row["id"],
        session_id=row["session_id"],
        version_id=row["version_id"],
        stage=row["stage"],
        status=row["status"],
        user_message=row["user_message"],
        details=_json_loads(row["details_json"], {}),
        created_at=row["created_at"],
    )


def emit_transparency_event(
    session_id: str,
    stage: str,
    status: TransparencyStatus,
    user_message: str,
    details: dict[str, Any] | None = None,
    version_id: str | None = None,
) -> TransparencyEventResponse:
    event_id = str(uuid.uuid4())
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO transparency_events (
                id,
                session_id,
                version_id,
                stage,
                status,
                user_message,
                details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                session_id,
                version_id,
                stage,
                status,
                user_message,
                _json_dumps(details or {}),
            ),
        )
        row = connection.execute(
            "SELECT * FROM transparency_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    return _transparency_event_from_row(row)


def list_transparency_events(session_id: str) -> list[TransparencyEventResponse]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM transparency_events
            WHERE session_id = ?
            ORDER BY rowid
            """,
            (session_id,),
        ).fetchall()
    return [_transparency_event_from_row(row) for row in rows]


def save_operational_plan(session_id: str, version_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(uuid.uuid4())
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO operational_plans (id, session_id, version_id, plan_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
              version_id = excluded.version_id,
              plan_json = excluded.plan_json,
              updated_at = CURRENT_TIMESTAMP
            """,
            (plan_id, session_id, version_id, _json_dumps(plan)),
        )
        row = connection.execute(
            "SELECT plan_json FROM operational_plans WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return _json_loads(row["plan_json"], plan) if row else plan


def get_operational_plan(session_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT plan_json FROM operational_plans WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return _json_loads(row["plan_json"], None) if row else None


def mark_protocol_session_accepted(session_id: str, version_id: str) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE protocol_versions SET status = CASE WHEN id = ? THEN 'accepted' ELSE status END WHERE session_id = ?",
            (version_id, session_id),
        )
        connection.execute(
            """
            UPDATE protocol_sessions
            SET status = 'accepted', accepted_version_id = ?
            WHERE id = ?
            """,
            (version_id, session_id),
        )


def stop_protocol_session(session_id: str) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE protocol_sessions SET status = 'stopped' WHERE id = ?",
            (session_id,),
        )


def _memory_text_for_feedback(session: dict[str, Any], feedback: ProtocolFeedbackResponse) -> str:
    hypothesis = session.get("structured_hypothesis") or {}
    context_parts = [
        str(hypothesis.get("domain") or "").strip(),
        str(hypothesis.get("model_system") or "").strip(),
        str(hypothesis.get("intervention") or "").strip(),
    ]
    context = " / ".join(part for part in context_parts if part) or "similar protocol drafts"
    correction = (feedback.feedback_text or "").strip()
    reason = (feedback.reason or "").strip()
    if reason:
        return f"For {context}, apply this researcher feedback in section {feedback.section}: {correction}. Rationale: {reason}"
    return f"For {context}, apply this researcher feedback in section {feedback.section}: {correction}"


def create_feedback_memories_for_session(session_id: str) -> list[FeedbackMemoryReference]:
    session = get_protocol_session_record(session_id)
    if not session:
        return []

    hypothesis = session.get("structured_hypothesis") or {}
    memories: list[FeedbackMemoryReference] = []
    reusable_feedback = [
        item
        for item in list_protocol_feedback(session_id, reusable_only=True)
        if (item.feedback_text or "").strip()
    ]

    with _connect() as connection:
        for feedback in reusable_feedback:
            memory_id = str(uuid.uuid4())
            memory_text = _memory_text_for_feedback(session, feedback)
            connection.execute(
                """
                INSERT OR IGNORE INTO feedback_memory (
                    id,
                    memory_text,
                    domain,
                    experiment_type,
                    model_system,
                    intervention,
                    outcome,
                    section,
                    source_feedback_id,
                    accepted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    memory_id,
                    memory_text,
                    hypothesis.get("domain"),
                    hypothesis.get("assay") or hypothesis.get("mechanism"),
                    hypothesis.get("model_system"),
                    hypothesis.get("intervention"),
                    hypothesis.get("outcome"),
                    feedback.section,
                    feedback.id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM feedback_memory WHERE source_feedback_id = ?",
                (feedback.id,),
            ).fetchone()
            if row:
                memories.append(_memory_from_row(row, search_backend="sqlite"))
    return memories


def _memory_from_row(row: sqlite3.Row, search_backend: str = "sqlite", distance: float | None = None) -> FeedbackMemoryReference:
    return FeedbackMemoryReference(
        id=row["id"],
        memory_text=row["memory_text"],
        domain=row["domain"],
        experiment_type=row["experiment_type"],
        model_system=row["model_system"],
        intervention=row["intervention"],
        outcome=row["outcome"],
        section=row["section"],
        distance=distance,
        search_backend=search_backend,
    )


def mark_feedback_memory_indexed(memory_id: str) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE feedback_memory SET chroma_indexed = 1 WHERE id = ?",
            (memory_id,),
        )


def list_feedback_memories() -> list[FeedbackMemoryReference]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM feedback_memory WHERE accepted = 1 ORDER BY created_at DESC",
        ).fetchall()
    return [_memory_from_row(row) for row in rows]


def search_feedback_memories_sqlite(
    structured_hypothesis: dict[str, Any],
    limit: int = 5,
) -> list[FeedbackMemoryReference]:
    memories = list_feedback_memories()
    if not memories:
        return []

    keywords = structured_hypothesis.get("keywords") or []
    query_values = [
        structured_hypothesis.get("domain"),
        structured_hypothesis.get("model_system"),
        structured_hypothesis.get("intervention"),
        structured_hypothesis.get("outcome"),
        structured_hypothesis.get("assay"),
        structured_hypothesis.get("mechanism"),
        *keywords,
    ]
    query_text = " ".join(str(value) for value in query_values if value)

    def tokenize(value: str) -> list[str]:
        return [
            token
            for token in re.findall(r"[a-z0-9/-]+", value.lower())
            if len(token) > 2
            and token
            not in {"the", "and", "for", "with", "protocol", "protocols", "from"}
        ]

    documents = [
        " ".join(
            value or ""
            for value in [
                memory.memory_text,
                memory.domain,
                memory.experiment_type,
                memory.model_system,
                memory.intervention,
                memory.outcome,
                memory.section,
            ]
        )
        for memory in memories
    ]
    tokenized_docs = [tokenize(document) for document in documents]
    query_tokens = tokenize(query_text)

    try:
        from rank_bm25 import BM25Okapi

        bm25_scores = BM25Okapi(tokenized_docs).get_scores(query_tokens) if query_tokens else []
    except Exception:
        bm25_scores = [0.0 for _ in memories]

    try:
        from rapidfuzz import fuzz, utils
    except Exception:
        fuzz = None
        utils = None

    def metadata_score(memory: FeedbackMemoryReference) -> float:
        score = 0.0
        metadata_pairs = [
            ("domain", structured_hypothesis.get("domain"), memory.domain),
            ("model_system", structured_hypothesis.get("model_system"), memory.model_system),
            ("intervention", structured_hypothesis.get("intervention"), memory.intervention),
            ("outcome", structured_hypothesis.get("outcome"), memory.outcome),
            ("experiment_type", structured_hypothesis.get("assay") or structured_hypothesis.get("mechanism"), memory.experiment_type),
        ]
        for _, expected, actual in metadata_pairs:
            if expected and actual and str(expected).lower() == str(actual).lower():
                score += 1.0
        return score

    scored: list[tuple[float, FeedbackMemoryReference]] = []
    max_bm25 = max(bm25_scores) if len(bm25_scores) else 0
    for index, memory in enumerate(memories):
        normalized_bm25 = (float(bm25_scores[index]) / max_bm25) if max_bm25 > 0 else 0.0
        fuzzy_score = (
            fuzz.token_set_ratio(query_text, documents[index], processor=utils.default_process) / 100
            if fuzz and utils and query_text
            else 0.0
        )
        total = (0.55 * normalized_bm25) + (0.25 * fuzzy_score) + (0.20 * metadata_score(memory))
        if total > 0:
            scored.append(
                (
                    total,
                    memory.model_copy(update={"search_backend": "sqlite_bm25_rapidfuzz"}),
                )
            )

    scored.sort(key=lambda item: item[0], reverse=True)
    return [memory for _, memory in scored[:limit]]
