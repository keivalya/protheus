from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.services.hypothesis import FIELD_NAMES

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"

STRUCTURED_HYPOTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "domain": {"type": ["string", "null"]},
        "model_system": {"type": ["string", "null"]},
        "intervention": {"type": ["string", "null"]},
        "control": {"type": ["string", "null"]},
        "outcome": {"type": ["string", "null"]},
        "effect_size": {"type": ["string", "null"]},
        "assay": {"type": ["string", "null"]},
        "mechanism": {"type": ["string", "null"]},
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 14,
        },
    },
    "required": FIELD_NAMES,
}

SYSTEM_PROMPT = """
You structure scientific hypotheses for a literature novelty-check app.

Extract only what is present in the user hypothesis or directly implied by standard scientific wording.
Use null when a field is not known. Do not invent missing controls, assays, effect sizes, mechanisms, or model systems.
Keep values concise and searchable. For keywords, include concrete entities, methods, model systems, interventions, controls, and outcomes from the hypothesis.
Keep outcome separate from quantitative thresholds, time limits, and comparison sizes. Put values like "below 0.5 mg/L", "within 10 minutes", "at least 15 percentage points", or "30 percent" in effect_size, not outcome.
""".strip()


def _output_text(response_data: dict[str, Any]) -> str | None:
    direct_text = response_data.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    text_chunks: list[str] = []
    for output_item in response_data.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                text_chunks.append(text)
    return "\n".join(text_chunks).strip() or None


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    normalized: dict[str, Any] = {}
    for field in FIELD_NAMES:
        value = payload.get(field)
        if field == "keywords":
            if isinstance(value, list):
                normalized[field] = [str(item).strip() for item in value if str(item).strip()][:14]
            else:
                normalized[field] = []
            continue
        normalized[field] = value.strip() if isinstance(value, str) and value.strip() else None
    return normalized


def structure_hypothesis_with_openai(query: str) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    request_body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": query}],
            },
        ],
        "max_output_tokens": 2200,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "structured_hypothesis",
                "strict": True,
                "schema": STRUCTURED_HYPOTHESIS_SCHEMA,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=18.0) as client:
        response = client.post(OPENAI_RESPONSES_URL, headers=headers, json=request_body)
        response.raise_for_status()

    text = _output_text(response.json())
    if not text:
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return _normalize_payload(payload)
