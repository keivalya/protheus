from __future__ import annotations

import os
from typing import Any
import httpx

VENDOR_DOMAINS = {
    "Thermo Fisher": "thermofisher.com",
    "Sigma-Aldrich": "sigmaaldrich.com",
    "Promega": "promega.com",
    "Qiagen": "qiagen.com",
    "IDT": "idtdna.com",
    "Fisher Scientific": "fishersci.com",
    "VWR": "vwr.com",
    "Bio-Rad": "bio-rad.com",
    "NEB": "neb.com",
}


def _vendor_logo_url(domain: str | None) -> str | None:
    if not domain:
        return None
    return f"https://www.google.com/s2/favicons?sz=128&domain={domain}"


def _google_image_search(query: str, allowed_domain: str | None = None) -> str | None:
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    if not api_key or not cse_id:
        return None

    scoped_query = f"{query} site:{allowed_domain}" if allowed_domain else query
    params = {
        "key": api_key,
        "cx": cse_id,
        "searchType": "image",
        "q": scoped_query,
        "num": 1,
        "safe": "active",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get("https://www.googleapis.com/customsearch/v1", params=params)
            response.raise_for_status()
        items = response.json().get("items") or []
        if not items:
            return None
        image_url = items[0].get("link")
        return image_url if isinstance(image_url, str) and image_url.startswith("http") else None
    except Exception:
        return None


def resolve_image(
    item: dict[str, Any],
    vendor: str | None,
    supplier_domain: str | None,
    product_name: str | None = None,
    candidate_image_url: str | None = None,
) -> dict[str, str | None]:
    if candidate_image_url and candidate_image_url.startswith("http"):
        return {
            "image_url": candidate_image_url,
            "image_status": "product_image_found",
        }

    domain = supplier_domain or VENDOR_DOMAINS.get(vendor or "")
    product_image = _google_image_search(
        " ".join(part for part in [vendor, product_name or item.get("item_name")] if part),
        domain,
    )
    if product_image:
        return {
            "image_url": product_image,
            "image_status": "product_image_found",
        }

    logo_url = _vendor_logo_url(domain)
    if logo_url:
        return {
            "image_url": logo_url,
            "image_status": "vendor_logo_only",
        }

    return {
        "image_url": None,
        "image_status": "category_icon_only",
    }
