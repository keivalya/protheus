from __future__ import annotations

import os
from typing import Any

from app.services.budget_calculator import calculate_budget
from app.services.material_extractor import extract_materials
from app.services.product_resolver import resolve_products
from app.services.protocol_models import ProtocolVersionResponse
from app.services.timeline_planner import build_timeline

GLOBAL_PRICE_WARNING = (
    "Prices are rough planning estimates, not procurement quotes. Final pricing may vary by institution, "
    "region, package size, shipping, taxes and availability."
)


def _max_web_search_items() -> int:
    raw_value = os.getenv("OPERATIONAL_PLAN_MAX_WEB_SEARCH_ITEMS")
    if not raw_value:
        return 5
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 5


def compile_operational_plan(
    session: dict[str, Any],
    accepted_version: ProtocolVersionResponse,
    schedule: dict[str, Any],
) -> dict[str, Any]:
    extracted_items = extract_materials(
        accepted_version,
        session.get("selected_protocols") or [],
    )
    max_web_items = _max_web_search_items()
    resolved_items = resolve_products(extracted_items, max_web_search_items=max_web_items)
    budget_summary, budget_breakdown, supply_chain_items = calculate_budget(resolved_items)
    timeline_payload = build_timeline(accepted_version, schedule)

    warnings = [GLOBAL_PRICE_WARNING]
    if not extracted_items:
        warnings.append("No material list was found in the accepted protocol or selected protocol evidence.")
    if max_web_items <= 0 and extracted_items:
        warnings.append(
            "Live supplier pricing was not run for this plan. Supplier cards use search links and require procurement confirmation."
        )
    elif len(extracted_items) > max_web_items:
        warnings.append(
            f"Live product web search was limited to the first {max_web_items} material items; remaining items use supplier search links and require procurement confirmation."
        )
    if budget_summary["missing_prices"]:
        warnings.append(
            f"{budget_summary['missing_prices']} item(s) have no confirmed public price and are excluded from the subtotal."
        )
    if budget_summary["excluded_due_to_missing_quantity"]:
        warnings.append(
            f"{budget_summary['excluded_due_to_missing_quantity']} item(s) use a one-package quantity assumption until procurement confirms the real amount."
        )

    assumptions = [
        "Operational plan starts only after the custom protocol is accepted.",
        "No purchasing is automated; supplier cards are planning references only.",
        f"Live public price lookup is limited to the first {max_web_items} material item(s) by default.",
        "Material extraction merges accepted protocol materials with selected protocols.io material previews when available.",
        *timeline_payload["assumptions"],
    ]

    return {
        "session_id": session["id"],
        "version_id": accepted_version.id,
        "supply_chain_items": supply_chain_items,
        "budget_summary": budget_summary,
        "budget_breakdown": budget_breakdown,
        "timeline": timeline_payload["timeline"],
        "assumptions": assumptions,
        "warnings": warnings,
    }
