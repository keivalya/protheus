from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.services.image_resolver import VENDOR_DOMAINS, resolve_image
from app.services.price_estimator import estimate_price

SUPPLIER_DOMAINS = [
    "thermofisher.com",
    "sigmaaldrich.com",
    "promega.com",
    "qiagen.com",
    "idtdna.com",
    "fishersci.com",
    "vwr.com",
    "bio-rad.com",
    "neb.com",
]

DOMAIN_VENDOR = {domain: vendor for vendor, domain in VENDOR_DOMAINS.items()}

SEARCH_URLS = {
    "thermofisher.com": "https://www.thermofisher.com/search/results?keyword={query}",
    "sigmaaldrich.com": "https://www.sigmaaldrich.com/US/en/search/{query}",
    "promega.com": "https://www.promega.com/search/?q={query}",
    "qiagen.com": "https://www.qiagen.com/us/search?query={query}",
    "idtdna.com": "https://www.idtdna.com/pages/search-results?searchString={query}",
    "fishersci.com": "https://www.fishersci.com/us/en/catalog/search/products?keyword={query}",
    "vwr.com": "https://us.vwr.com/store/product?keyword={query}",
    "bio-rad.com": "https://www.bio-rad.com/search-results?search_api_fulltext={query}",
    "neb.com": "https://www.neb.com/search#q={query}",
}


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain in SUPPLIER_DOMAINS:
        if host == domain or host.endswith(f".{domain}"):
            return domain
    return host or None


def _search_url(domain: str, item_name: str, catalog_number: str | None = None) -> str:
    query = quote_plus(catalog_number or item_name)
    template = SEARCH_URLS.get(domain)
    if template:
        return template.format(query=query)
    return f"https://{domain}/search?q={query}"


def _vendor_candidates(item: dict[str, Any]) -> list[tuple[str, str]]:
    explicit_domain = item.get("supplier_domain") or _domain_from_url(item.get("product_url"))
    explicit_vendor = item.get("vendor") or DOMAIN_VENDOR.get(explicit_domain or "")
    if explicit_vendor and explicit_domain:
        return [(explicit_vendor, explicit_domain)]

    item_name = item["item_name"].lower()
    category = item.get("category")
    if "primer" in item_name or "oligo" in item_name or "gblock" in item_name:
        domains = ["idtdna.com", "thermofisher.com"]
    elif "enzyme" in item_name or "polymerase" in item_name or "nebnext" in item_name:
        domains = ["neb.com", "thermofisher.com"]
    elif category == "kits_and_assays":
        domains = ["qiagen.com", "promega.com", "thermofisher.com"]
    elif category == "consumables":
        domains = ["fishersci.com", "vwr.com", "thermofisher.com"]
    elif category == "equipment_usage":
        domains = ["bio-rad.com", "thermofisher.com", "fishersci.com"]
    else:
        domains = ["sigmaaldrich.com", "thermofisher.com", "fishersci.com"]
    return [(DOMAIN_VENDOR[domain], domain) for domain in domains if domain in DOMAIN_VENDOR]


def resolve_product(item: dict[str, Any], allow_web_search: bool = True) -> dict[str, Any]:
    candidates = _vendor_candidates(item)
    primary_vendor, primary_domain = candidates[0] if candidates else (None, None)
    fallback_url = item.get("product_url")
    if not fallback_url and primary_domain:
        fallback_url = _search_url(primary_domain, item["item_name"], item.get("catalog_number"))

    price_payload = estimate_price(
        item,
        primary_vendor,
        primary_domain,
        fallback_url,
        SUPPLIER_DOMAINS,
        allow_web_search=allow_web_search,
    )
    vendor = price_payload.get("vendor") or primary_vendor
    product_url = price_payload.get("product_url") or fallback_url
    supplier_domain = _domain_from_url(product_url) or primary_domain

    image_payload = resolve_image(
        item,
        vendor,
        supplier_domain,
        product_name=price_payload.get("product_name"),
    )

    candidate = {
        **price_payload,
        "vendor": vendor,
        "product_url": product_url,
        "image_url": image_payload["image_url"],
        "image_status": image_payload["image_status"],
    }
    return {
        **item,
        "supplier_candidates": [candidate],
    }


def resolve_products(items: list[dict[str, Any]], max_web_search_items: int | None = None) -> list[dict[str, Any]]:
    if not items:
        return []

    def resolve_indexed(indexed_item: tuple[int, dict[str, Any]]) -> dict[str, Any]:
        index, item = indexed_item
        allow_web_search = max_web_search_items is None or index <= max_web_search_items
        return resolve_product(item, allow_web_search=allow_web_search)

    max_workers = min(4, len(items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(resolve_indexed, enumerate(items, start=1)))
