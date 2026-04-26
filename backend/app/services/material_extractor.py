from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlparse

from app.services.protocol_models import ProtocolVersionResponse

MATERIAL_SECTION_KEYS = [
    "materials",
    "materials_preview",
    "reagents",
    "consumables",
    "equipment",
    "kits",
    "assay_kits",
]

CATALOG_RE = re.compile(
    r"\b(?:cat(?:alog)?\.?\s*(?:no\.?|number)?|sku|part(?:\s*no\.?)?)\s*[:#-]?\s*([A-Za-z0-9._/-]{3,})",
    re.IGNORECASE,
)
QUANTITY_COUNT_RE = re.compile(
    r"\b(?P<count>\d+(?:\.\d+)?)\s*(?P<unit>kits?|packs?|boxes?|bottles?|vials?|tubes?|plates?|reactions?|runs?|assays?)\b",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:uL|µL|mL|L|mg|g|kg|ng|ug|µg|nmol|pmol)\b",
    re.IGNORECASE,
)

SUPPLIER_DOMAINS = {
    "thermofisher.com": "Thermo Fisher",
    "sigmaaldrich.com": "Sigma-Aldrich",
    "promega.com": "Promega",
    "qiagen.com": "Qiagen",
    "idtdna.com": "IDT",
    "fishersci.com": "Fisher Scientific",
    "vwr.com": "VWR",
    "bio-rad.com": "Bio-Rad",
    "neb.com": "NEB",
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _clean_material_name(raw_value: str) -> str:
    value = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw_value).strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\((?:cat(?:alog)?\.?|sku|part).*?\)", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\b(?:cat(?:alog)?\.?\s*(?:no\.?|number)?|sku|part(?:\s*no\.?)?)\s*[:#-]?\s*[A-Za-z0-9._/-]{3,}", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s+from\s+[A-Z][A-Za-z0-9 &.-]{2,}$", "", value).strip()
    return value.strip(" ,;:-")


def _quantity_from_text(raw_value: str) -> tuple[str, float | None, list[str]]:
    count_match = QUANTITY_COUNT_RE.search(raw_value)
    if count_match:
        count = float(count_match.group("count"))
        quantity = count_match.group(0)
        return quantity, max(1.0, math.ceil(count)), []

    amount_match = AMOUNT_RE.search(raw_value)
    if amount_match:
        return (
            amount_match.group(0),
            1.0,
            ["Budget uses one purchasable package because protocol amount is present but package mapping is unavailable."],
        )

    return "missing information", None, []


def _catalog_number(raw_value: str) -> str | None:
    match = CATALOG_RE.search(raw_value)
    return match.group(1) if match else None


def _supplier_from_url(url: str | None) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain, vendor in SUPPLIER_DOMAINS.items():
        if host == domain or host.endswith(f".{domain}"):
            return vendor, domain
    return None, host or None


def _category_for_item(name: str, source_kind: str | None = None) -> str:
    lowered = name.lower()
    if source_kind == "equipment" or any(
        term in lowered
        for term in [
            "microscope",
            "incubator",
            "centrifuge",
            "plate reader",
            "thermocycler",
            "thermal cycler",
            "sequencer",
            "spectrophotometer",
            "flow cytometer",
            "biosafety cabinet",
            "pipette",
        ]
    ):
        return "equipment_usage"
    if any(term in lowered for term in ["kit", "assay", "qpcr", "elisa", "sequencing library"]):
        return "kits_and_assays"
    if any(
        term in lowered
        for term in [
            "cell line",
            "cells",
            "organoid",
            "spheroid",
            "strain",
            "plasmid",
            "virus",
            "bacteria",
            "serum",
            "antibody",
            "primer",
            "oligo",
            "grna",
            "sirna",
        ]
    ):
        return "cell_lines_biological_materials"
    if any(
        term in lowered
        for term in [
            "plate",
            "tube",
            "flask",
            "dish",
            "tip",
            "filter",
            "membrane",
            "syringe",
            "vial",
            "slide",
            "cover glass",
            "well",
        ]
    ):
        return "consumables"
    return "reagents_chemicals"


def _iter_selected_protocol_materials(protocol: dict[str, Any]) -> list[tuple[str, str | None, dict[str, Any]]]:
    extracted: list[tuple[str, str | None, dict[str, Any]]] = []
    for key in MATERIAL_SECTION_KEYS:
        value = protocol.get(key)
        if not value:
            continue
        source_kind = "equipment" if key == "equipment" else None
        if isinstance(value, str):
            extracted.extend((line, source_kind, {}) for line in _split_material_text(value))
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    extracted.append((item, source_kind, {}))
                elif isinstance(item, dict):
                    name = _safe_text(
                        item.get("name")
                        or item.get("item_name")
                        or item.get("material")
                        or item.get("title")
                    )
                    if name:
                        extracted.append((name, source_kind, item))
    return extracted


def _split_material_text(value: str) -> list[str]:
    lines: list[str] = []
    for raw_line in re.split(r"[\n\r]+", value):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) > 120 and ";" in line:
            lines.extend(part.strip() for part in line.split(";") if part.strip())
        elif len(line) <= 120:
            lines.append(line)
    return lines


def _add_item(
    items_by_key: dict[str, dict[str, Any]],
    raw_name: str,
    source_id: str,
    source_kind: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    metadata = metadata or {}
    cleaned_name = _clean_material_name(raw_name)
    if len(cleaned_name) < 2:
        return

    key = _normalize_key(cleaned_name)
    if not key:
        return

    quantity_needed, quantity_multiplier, quantity_notes = _quantity_from_text(raw_name)
    product_url = _safe_text(metadata.get("url") or metadata.get("product_url")) or None
    vendor, supplier_domain = _supplier_from_url(product_url)
    vendor = _safe_text(metadata.get("vendor") or metadata.get("supplier") or vendor) or None
    catalog_number = _safe_text(
        metadata.get("catalog_number") or metadata.get("catalog") or metadata.get("sku")
    ) or _catalog_number(raw_name)

    existing = items_by_key.get(key)
    if existing:
        if source_id not in existing["source_ids"]:
            existing["source_ids"].append(source_id)
        if existing["quantity_multiplier"] is None and quantity_multiplier is not None:
            existing["quantity_needed"] = quantity_needed
            existing["quantity_multiplier"] = quantity_multiplier
        if vendor and not existing.get("vendor"):
            existing["vendor"] = vendor
        if supplier_domain and not existing.get("supplier_domain"):
            existing["supplier_domain"] = supplier_domain
        if catalog_number and not existing.get("catalog_number"):
            existing["catalog_number"] = catalog_number
        if product_url and not existing.get("product_url"):
            existing["product_url"] = product_url
        for note in quantity_notes:
            if note not in existing["notes"]:
                existing["notes"].append(note)
        return

    items_by_key[key] = {
        "item_name": cleaned_name,
        "category": _category_for_item(cleaned_name, source_kind),
        "quantity_needed": quantity_needed,
        "quantity_multiplier": quantity_multiplier,
        "source_ids": [source_id],
        "vendor": vendor,
        "supplier_domain": supplier_domain,
        "catalog_number": catalog_number,
        "product_url": product_url,
        "supplier_candidates": [],
        "notes": [
            "Rough planning estimate only. Final price may vary by institution, region, shipping, taxes and availability.",
            *quantity_notes,
        ],
    }


def extract_materials(
    accepted_version: ProtocolVersionResponse,
    selected_protocols: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    protocol = accepted_version.protocol
    items_by_key: dict[str, dict[str, Any]] = {}

    for item in protocol.materials_and_reagents.items:
        _add_item(
            items_by_key,
            item.name,
            item.source_ids[0] if item.source_ids else f"accepted_protocol:{accepted_version.id}",
        )

    for line in _split_material_text(protocol.materials_and_reagents.content):
        _add_item(items_by_key, line, f"accepted_protocol:{accepted_version.id}")

    for evidence in protocol.extracted_protocol_evidence:
        for material in evidence.materials:
            _add_item(items_by_key, material, evidence.source_id)
        for equipment in evidence.equipment:
            _add_item(items_by_key, equipment, evidence.source_id, source_kind="equipment")

    for index, selected_protocol in enumerate(selected_protocols, start=1):
        source_id = (
            selected_protocol.get("id")
            or selected_protocol.get("url")
            or selected_protocol.get("title")
            or f"selected_protocol:{index}"
        )
        for material, source_kind, metadata in _iter_selected_protocol_materials(selected_protocol):
            _add_item(items_by_key, material, str(source_id), source_kind=source_kind, metadata=metadata)

    return sorted(items_by_key.values(), key=lambda item: (item["category"], item["item_name"].lower()))
