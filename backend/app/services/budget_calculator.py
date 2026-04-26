from __future__ import annotations

from collections import defaultdict
from typing import Any

CATEGORY_LABELS = {
    "reagents_chemicals": "Reagents and chemicals",
    "consumables": "Consumables",
    "cell_lines_biological_materials": "Cell lines / biological materials",
    "kits_and_assays": "Kits and assay reagents",
    "equipment_usage": "Equipment usage or rental",
    "external_services": "External services",
}


def _first_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    candidates = item.get("supplier_candidates") or []
    return candidates[0] if candidates else None


def _price_range(candidate: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not candidate:
        return None, None
    price_range = candidate.get("estimated_price_range") or {}
    min_price = price_range.get("min")
    max_price = price_range.get("max")
    if not isinstance(min_price, (int, float)) or not isinstance(max_price, (int, float)):
        return None, None
    return float(min_price), float(max_price)


def calculate_budget(items: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    category_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "category": "",
            "label": "",
            "min": 0.0,
            "max": 0.0,
            "currency": "USD",
            "items_count": 0,
            "excluded_count": 0,
        }
    )

    priced_items = 0
    missing_prices = 0
    excluded_missing_quantity = 0
    annotated_items: list[dict[str, Any]] = []

    for item in items:
        candidate = _first_candidate(item)
        min_price, max_price = _price_range(candidate)
        quantity_multiplier = item.get("quantity_multiplier")
        has_price = min_price is not None and max_price is not None
        has_quantity = isinstance(quantity_multiplier, (int, float)) and quantity_multiplier > 0
        category = item.get("category") or "reagents_chemicals"
        category_total = category_totals[category]
        category_total["category"] = category
        category_total["label"] = CATEGORY_LABELS.get(category, category.replace("_", " "))

        budget_status = "included"
        item_cost_min = None
        item_cost_max = None
        item_notes = list(item.get("notes") or [])
        if has_price:
            quantity_for_budget = float(quantity_multiplier) if has_quantity else 1.0
            priced_items += 1
            item_cost_min = round(float(min_price) * quantity_for_budget, 2)
            item_cost_max = round(float(max_price) * quantity_for_budget, 2)
            category_total["min"] += item_cost_min
            category_total["max"] += item_cost_max
            category_total["items_count"] += 1
            if not has_quantity:
                excluded_missing_quantity += 1
                budget_status = "missing_quantity"
                item_notes.append(
                    "Budget assumes one purchasable package because protocol quantity is missing."
                )
        else:
            category_total["excluded_count"] += 1
            if not has_price:
                missing_prices += 1
                budget_status = "missing_price"
            if not has_quantity:
                excluded_missing_quantity += 1
                budget_status = (
                    "missing_price_and_quantity"
                    if budget_status == "missing_price"
                    else "missing_quantity"
                )

        annotated_items.append(
            {
                **item,
                "notes": item_notes,
                "budget_status": budget_status,
                "item_cost_range": {
                    "min": item_cost_min,
                    "max": item_cost_max,
                    "currency": "USD",
                },
            }
        )

    subtotal_min = round(sum(entry["min"] for entry in category_totals.values()), 2)
    subtotal_max = round(sum(entry["max"] for entry in category_totals.values()), 2)
    shipping_min = round(subtotal_min * 0.08, 2) if subtotal_min else 0.0
    shipping_max = round(subtotal_max * 0.08, 2) if subtotal_max else 0.0
    contingency_min = round((subtotal_min + shipping_min) * 0.10, 2) if subtotal_min else 0.0
    contingency_max = round((subtotal_max + shipping_max) * 0.20, 2) if subtotal_max else 0.0
    total_min = round(subtotal_min + shipping_min + contingency_min, 2)
    total_max = round(subtotal_max + shipping_max + contingency_max, 2)

    breakdown = [
        {
            **entry,
            "min": round(entry["min"], 2),
            "max": round(entry["max"], 2),
        }
        for entry in category_totals.values()
        if entry["items_count"] or entry["excluded_count"]
    ]
    breakdown.extend(
        [
            {
                "category": "shipping_taxes_estimate",
                "label": "Shipping/taxes estimate",
                "min": shipping_min,
                "max": shipping_max,
                "currency": "USD",
                "items_count": priced_items,
                "excluded_count": 0,
            },
            {
                "category": "contingency",
                "label": "Contingency",
                "min": contingency_min,
                "max": contingency_max,
                "currency": "USD",
                "items_count": priced_items,
                "excluded_count": 0,
            },
        ]
    )

    confidence = "high"
    if not items or priced_items < len(items):
        confidence = "medium" if priced_items >= max(1, len(items) // 2) else "low"
    if excluded_missing_quantity:
        confidence = "medium" if confidence == "high" else confidence

    summary = {
        "estimated_total_range": {
            "min": total_min,
            "max": total_max,
            "currency": "USD",
        },
        "subtotal_range": {
            "min": subtotal_min,
            "max": subtotal_max,
            "currency": "USD",
        },
        "priced_items": priced_items,
        "total_items": len(items),
        "missing_prices": missing_prices,
        "excluded_due_to_missing_quantity": excluded_missing_quantity,
        "confidence": confidence,
        "notes": [
            "Planning estimate only. Items with missing quantities use one purchasable package until procurement confirms the real amount.",
            "Items with missing prices are excluded from the subtotal.",
            "Shipping/taxes are estimated at 8%; contingency uses 10% to 20%.",
        ],
    }
    return summary, breakdown, annotated_items
