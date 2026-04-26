from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import httpx

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_PRODUCT_SEARCH_MODEL = "gpt-5-mini"

PRICE_STATUSES = {
    "rough_web_estimate",
    "catalog_only",
    "price_not_found",
    "multiple_prices_found",
    "needs_procurement_confirmation",
}

CATEGORY_BENCHMARK_RANGES: dict[str, tuple[float, float]] = {
    "reagents_chemicals": (40.0, 250.0),
    "consumables": (25.0, 180.0),
    "cell_lines_biological_materials": (300.0, 1500.0),
    "kits_and_assays": (250.0, 900.0),
    "equipment_usage": (150.0, 1200.0),
    "external_services": (500.0, 5000.0),
}

KEYWORD_BENCHMARK_RANGES: list[tuple[tuple[str, ...], tuple[float, float], str]] = [
    (("antibody", "antibodies"), (300.0, 700.0), "common antibody price range"),
    (("assay", "kit", "viability"), (250.0, 850.0), "common kit or assay price range"),
    (("medium", "media", "supplement"), (60.0, 350.0), "common cell-culture media or supplement range"),
    (("trehalose", "sucrose", "dmso", "buffer"), (30.0, 180.0), "common reagent bottle range"),
    (("cell", "cells", "hela", "hipsc", "organoid"), (300.0, 1500.0), "common biological material range"),
    (("plate", "tube", "tip", "flask", "dish"), (25.0, 180.0), "common consumable package range"),
]

PRICE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "vendor": {"type": ["string", "null"]},
        "product_name": {"type": ["string", "null"]},
        "catalog_number": {"type": ["string", "null"]},
        "package_size": {"type": ["string", "null"]},
        "estimated_price_min": {"type": ["number", "null"]},
        "estimated_price_max": {"type": ["number", "null"]},
        "currency": {"type": "string"},
        "price_status": {
            "type": "string",
            "enum": [
                "rough_web_estimate",
                "catalog_only",
                "price_not_found",
                "multiple_prices_found",
                "needs_procurement_confirmation",
            ],
        },
        "product_url": {"type": ["string", "null"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "notes": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 4,
        },
    },
    "required": [
        "vendor",
        "product_name",
        "catalog_number",
        "package_size",
        "estimated_price_min",
        "estimated_price_max",
        "currency",
        "price_status",
        "product_url",
        "confidence",
        "notes",
    ],
}


def _web_search_enabled() -> bool:
    configured = os.getenv("ENABLE_PRODUCT_WEB_SEARCH")
    if configured is not None:
        return configured.lower() in {"1", "true", "yes", "on"}
    return bool(os.getenv("OPENAI_API_KEY"))


def _benchmark_estimates_enabled() -> bool:
    configured = os.getenv("ENABLE_BENCHMARK_PRICE_ESTIMATES")
    if configured is not None:
        return configured.lower() in {"1", "true", "yes", "on"}
    return True


def _output_text(response_data: dict[str, Any]) -> str | None:
    direct_text = response_data.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    chunks: list[str] = []
    for output_item in response_data.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text)
    return "\n".join(chunks).strip() or None


def _json_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if "\n" in stripped:
            stripped = stripped.split("\n", 1)[1]
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _source_urls(response_data: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for output_item in response_data.get("output", []):
        if not isinstance(output_item, dict):
            continue
        action = output_item.get("action")
        if isinstance(action, dict):
            for source in action.get("sources") or []:
                if isinstance(source, dict):
                    url = source.get("url")
                    if isinstance(url, str) and url.startswith("http") and url not in urls:
                        urls.append(url)
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            for annotation in content_item.get("annotations") or []:
                if isinstance(annotation, dict):
                    url = annotation.get("url")
                    if isinstance(url, str) and url.startswith("http") and url not in urls:
                        urls.append(url)
    return urls


def _normalize_price_payload(
    payload: dict[str, Any],
    fallback_vendor: str | None,
    fallback_product_name: str,
    fallback_catalog_number: str | None,
    fallback_product_url: str | None,
    sources: list[str],
) -> dict[str, Any]:
    status = str(payload.get("price_status") or "price_not_found")
    if status not in PRICE_STATUSES:
        status = "price_not_found"

    min_price = payload.get("estimated_price_min")
    max_price = payload.get("estimated_price_max")
    if not isinstance(min_price, (int, float)) or not isinstance(max_price, (int, float)):
        min_price = None
        max_price = None
    elif min_price > max_price:
        min_price, max_price = max_price, min_price

    product_url = payload.get("product_url") if isinstance(payload.get("product_url"), str) else None
    if not product_url and sources:
        product_url = sources[0]

    return {
        "vendor": payload.get("vendor") or fallback_vendor,
        "product_name": payload.get("product_name") or fallback_product_name,
        "catalog_number": payload.get("catalog_number") or fallback_catalog_number,
        "package_size": payload.get("package_size"),
        "estimated_price_range": {
            "min": round(float(min_price), 2) if min_price is not None else None,
            "max": round(float(max_price), 2) if max_price is not None else None,
            "currency": payload.get("currency") or "USD",
        },
        "price_status": status,
        "product_url": product_url or fallback_product_url,
        "confidence": payload.get("confidence") or "low",
        "last_checked": date.today().isoformat(),
        "source_urls": sources,
        "notes": payload.get("notes") if isinstance(payload.get("notes"), list) else [],
    }


def _benchmark_price_estimate(
    item: dict[str, Any],
    vendor: str | None,
    product_url: str | None,
) -> dict[str, Any] | None:
    if not _benchmark_estimates_enabled():
        return None

    item_name = item["item_name"]
    lowered = item_name.lower()
    note = "Category-level benchmark planning estimate."
    price_min, price_max = CATEGORY_BENCHMARK_RANGES.get(
        item.get("category") or "reagents_chemicals",
        (50.0, 500.0),
    )

    for keywords, price_range, reason in KEYWORD_BENCHMARK_RANGES:
        if any(keyword in lowered for keyword in keywords):
            price_min, price_max = price_range
            note = reason
            break

    return {
        "vendor": vendor,
        "product_name": item_name,
        "catalog_number": item.get("catalog_number"),
        "package_size": item.get("quantity_needed") if item.get("quantity_needed") != "missing" else None,
        "estimated_price_range": {
            "min": price_min,
            "max": price_max,
            "currency": "USD",
        },
        "price_status": "needs_procurement_confirmation",
        "product_url": product_url,
        "confidence": "low",
        "last_checked": date.today().isoformat(),
        "source_urls": [product_url] if product_url else [],
        "notes": [
            f"{note}; no confirmed public supplier price was found.",
            "Use this only for PI-level planning until procurement confirms institutional pricing and availability.",
        ],
    }


def _openai_price_search(
    item: dict[str, Any],
    vendor: str | None,
    supplier_domain: str | None,
    allowed_domains: list[str],
) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not _web_search_enabled():
        return None

    model = os.getenv("OPENAI_PRODUCT_SEARCH_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_PRODUCT_SEARCH_MODEL
    item_name = item["item_name"]
    catalog_number = item.get("catalog_number")
    input_text = (
        "Find a real supplier product page and rough public planning price for this lab supply item.\n"
        f"Item: {item_name}\n"
        f"Category: {item.get('category')}\n"
        f"Preferred vendor: {vendor or 'not specified'}\n"
        f"Catalog/SKU if known: {catalog_number or 'not specified'}\n"
        f"Existing product URL if known: {item.get('product_url') or 'not specified'}\n\n"
        "Use only visible supplier/catalog information. Do not invent prices. If price is hidden, unavailable, "
        "or requires institutional login, return null prices and an appropriate price_status. Prefer USD. "
        "Return the most specific package size and product URL you can verify."
    )

    tool: dict[str, Any] = {
        "type": "web_search",
        "filters": {
            "allowed_domains": allowed_domains,
        },
    }
    if supplier_domain and supplier_domain not in allowed_domains:
        tool["filters"]["allowed_domains"] = [supplier_domain, *allowed_domains]

    body = {
        "model": model,
        "tools": [tool],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are a procurement research assistant for scientific planning. "
                            "Return strict JSON matching the schema. Prices are rough planning estimates, "
                            "not quotes."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": input_text}],
            },
        ],
        "max_output_tokens": 1400,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "product_price_estimate",
                "strict": True,
                "schema": PRICE_SCHEMA,
            }
        },
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
        data = response.json()
        text = _output_text(data)
        payload = _json_from_text(text) if text else None
        if not payload:
            return None
        return _normalize_price_payload(
            payload,
            vendor,
            item_name,
            catalog_number,
            item.get("product_url"),
            _source_urls(data),
        )
    except Exception:
        return None


def estimate_price(
    item: dict[str, Any],
    vendor: str | None,
    supplier_domain: str | None,
    product_url: str | None,
    allowed_domains: list[str],
    allow_web_search: bool = True,
) -> dict[str, Any]:
    web_estimate = (
        _openai_price_search(item, vendor, supplier_domain, allowed_domains)
        if allow_web_search
        else None
    )
    if web_estimate:
        web_range = web_estimate.get("estimated_price_range") or {}
        if isinstance(web_range.get("min"), (int, float)) and isinstance(web_range.get("max"), (int, float)):
            return web_estimate
        benchmark_after_search = _benchmark_price_estimate(
            item,
            web_estimate.get("vendor") or vendor,
            web_estimate.get("product_url") or product_url,
        )
        if benchmark_after_search:
            benchmark_after_search["source_urls"] = list(
                dict.fromkeys(
                    [
                        *(web_estimate.get("source_urls") or []),
                        *(benchmark_after_search.get("source_urls") or []),
                    ]
                )
            )
            benchmark_after_search["notes"] = [
                "Public search did not expose a usable price.",
                *benchmark_after_search["notes"],
            ]
            return benchmark_after_search
        return web_estimate

    benchmark_estimate = _benchmark_price_estimate(item, vendor, product_url)
    if benchmark_estimate:
        return benchmark_estimate

    return {
        "vendor": vendor,
        "product_name": item["item_name"],
        "catalog_number": item.get("catalog_number"),
        "package_size": None,
        "estimated_price_range": {
            "min": None,
            "max": None,
            "currency": "USD",
        },
        "price_status": "catalog_only" if product_url else "price_not_found",
        "product_url": product_url,
        "confidence": "low",
        "last_checked": date.today().isoformat(),
        "source_urls": [product_url] if product_url else [],
        "notes": [
            "No public price was confirmed during automated planning. Procurement should confirm package size, contract pricing and availability."
        ],
    }
