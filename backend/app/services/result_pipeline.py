from collections import Counter
import re

from ..models.product import ProductListing
from .normalization import extract_brand, extract_quantity, normalize_text, tokens

FAMILY_RULES = (
    ("ketchup", {"ketchup", "sauce"}),
    ("atta_noodles", {"atta"}),
    ("noodles", {"noodles", "ramen", "pasta"}),
    ("seasoning", {"magic", "seasoning"}),
    ("butter", {"butter"}),
    ("milk", {"milk"}),
    ("bread", {"bread"}),
    ("eggs", {"eggs", "egg"}),
)


def product_family(title: str) -> str | None:
    title_tokens = tokens(title)
    for family, family_tokens in FAMILY_RULES:
        if title_tokens & family_tokens:
            return family
    return None


def provider_identity(listing: ProductListing) -> str:
    quantity = extract_quantity(listing.quantity_text or listing.title)
    brand = (listing.brand or extract_brand(listing.title) or "").lower()
    family = product_family(listing.title) or normalize_text(listing.title)
    variants = " ".join(sorted(tokens(listing.title) & {"masala", "cheese", "classic", "salted", "unsalted", "diet", "zero", "regular", "family", "sugarfree"}))
    pack_count = quantity.pack_count or 1
    value = quantity.total_value if quantity.total_value is not None else "unknown"
    unit = quantity.unit or "unknown"
    return f"{brand}|{family}|{variants}|{value}|{unit}|{pack_count}"


def deduplicate_listings(listings: list[ProductListing]) -> list[ProductListing]:
    selected: dict[str, ProductListing] = {}
    for listing in listings:
        key = provider_identity(listing)
        existing = selected.get(key)
        if existing is None or (listing.available and not existing.available):
            selected[key] = listing
    return list(selected.values())


def query_relevance(listing: ProductListing, query: str, position: int) -> float:
    query_tokens = tokens(query)
    title_tokens = tokens(listing.title)
    if not query_tokens:
        return 0.0
    coverage = len(query_tokens & title_tokens) / len(query_tokens)
    brand = (listing.brand or extract_brand(listing.title) or "").lower()
    brand_score = 1.0 if brand and brand in query_tokens else 0.0
    query_family = product_family(query)
    listing_family = product_family(listing.title)
    family_score = 1.0 if query_family and query_family == listing_family else 0.0
    from rapidfuzz.fuzz import token_set_ratio
    title_similarity = token_set_ratio(normalize_text(query), normalize_text(listing.title)) / 100
    position_score = max(0.0, 1.0 - min(position, 50) / 50) * 0.05
    return round(min(1.0, 0.50 * coverage + 0.20 * title_similarity + 0.15 * brand_score + 0.10 * family_score + position_score), 4)


def rank_by_query_relevance(listings: list[ProductListing], query: str) -> list[ProductListing]:
    ranked = []
    for position, listing in enumerate(listings):
        relevance = query_relevance(listing, query, position)
        ranked.append(listing.model_copy(update={"metadata": {**listing.metadata, "query_relevance_score": relevance, "provider_position": position}}))
    return sorted(ranked, key=lambda listing: (-listing.metadata["query_relevance_score"], listing.metadata["provider_position"]))


def pipeline_counts(raw: dict[str, int], deduplicated: dict[str, int], candidate_pairs: int, matched_pairs: int, returned_results: int) -> dict:
    return {
        "raw_counts": raw,
        "deduplicated_counts": deduplicated,
        "candidate_pairs": candidate_pairs,
        "matched_pairs": matched_pairs,
        "returned_results": returned_results,
    }
