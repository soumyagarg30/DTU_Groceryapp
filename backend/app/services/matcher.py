from dataclasses import dataclass

from rapidfuzz.fuzz import token_set_ratio

from ..models.product import ProductListing
from .normalization import extract_brand, extract_quantity, tokens
from .result_pipeline import product_family

IMPORTANT_VARIANTS = {"masala", "cheese", "classic", "salted", "unsalted", "diet", "zero", "regular", "family", "sugarfree", "atta", "tomato"}
VARIANT_CONFLICT_GROUPS = ({"salted", "unsalted"}, {"diet", "zero", "regular"}, {"masala", "atta"})


@dataclass(frozen=True)
class MatchBreakdown:
    brand_score: float
    quantity_score: float
    pack_score: float
    variant_score: float
    title_similarity: float
    conflicts: tuple[str, ...]
    final_confidence: float


@dataclass(frozen=True)
class ProductMatch:
    left: ProductListing
    right: ProductListing
    score: float
    confidence: str
    breakdown: MatchBreakdown


def _brand(listing: ProductListing) -> str:
    return (listing.brand or extract_brand(listing.title) or "").strip().lower()


def _variants(listing: ProductListing) -> set[str]:
    return tokens(listing.title) & IMPORTANT_VARIANTS


def _hard_conflicts(left: ProductListing, right: ProductListing) -> list[str]:
    conflicts: list[str] = []
    left_brand, right_brand = _brand(left), _brand(right)
    if left_brand and right_brand and left_brand != right_brand:
        conflicts.append("different known brands")
    left_family, right_family = product_family(left.title), product_family(right.title)
    if left_family and right_family and left_family != right_family:
        conflicts.append("incompatible product families")
    left_quantity = extract_quantity(left.quantity_text or left.title)
    right_quantity = extract_quantity(right.quantity_text or right.title)
    if left_quantity.unit and right_quantity.unit and left_quantity.unit != right_quantity.unit:
        conflicts.append("incompatible unit classes")
    elif left_quantity.total_value and right_quantity.total_value:
        ratio = min(left_quantity.total_value, right_quantity.total_value) / max(left_quantity.total_value, right_quantity.total_value)
        if ratio < 0.8:
            conflicts.append("materially different quantities")
    left_pack, right_pack = left_quantity.pack_count or 1, right_quantity.pack_count or 1
    if left_pack != right_pack and (left_quantity.pack_count or right_quantity.pack_count):
        conflicts.append("different pack structures")
    left_variants, right_variants = _variants(left), _variants(right)
    left_title_tokens, right_title_tokens = tokens(left.title), tokens(right.title)
    left_is_cup = bool(left_title_tokens & {"cup", "cuppa"})
    right_is_cup = bool(right_title_tokens & {"cup", "cuppa"})
    if left_is_cup != right_is_cup:
        conflicts.append("different product forms")
    for group in VARIANT_CONFLICT_GROUPS:
        left_group, right_group = left_variants & group, right_variants & group
        if left_group and right_group and left_group != right_group:
            conflicts.append("conflicting variants")
            break
    return conflicts


def _brand_score(left: ProductListing, right: ProductListing) -> float:
    left_brand, right_brand = _brand(left), _brand(right)
    if left_brand and right_brand:
        return 1.0 if left_brand == right_brand else 0.0
    return 0.5


def _quantity_score(left: ProductListing, right: ProductListing) -> float:
    left_quantity = extract_quantity(left.quantity_text or left.title)
    right_quantity = extract_quantity(right.quantity_text or right.title)
    if not left_quantity.unit or not right_quantity.unit:
        return 0.5
    if left_quantity.unit != right_quantity.unit or not left_quantity.total_value or not right_quantity.total_value:
        return 0.0
    if left_quantity.total_value == right_quantity.total_value:
        return 1.0
    ratio = min(left_quantity.total_value, right_quantity.total_value) / max(left_quantity.total_value, right_quantity.total_value)
    return 0.8 if ratio >= 0.9 else 0.0


def _pack_score(left: ProductListing, right: ProductListing) -> float:
    left_pack = extract_quantity(left.quantity_text or left.title).pack_count or 1
    right_pack = extract_quantity(right.quantity_text or right.title).pack_count or 1
    return 1.0 if left_pack == right_pack else 0.0


def _variant_score(left: ProductListing, right: ProductListing) -> float:
    left_variants, right_variants = _variants(left), _variants(right)
    if left_variants == right_variants:
        return 1.0
    if not left_variants or not right_variants:
        return 0.6
    return 0.5


def match_breakdown(left: ProductListing, right: ProductListing) -> MatchBreakdown:
    conflicts = tuple(_hard_conflicts(left, right))
    brand_score = _brand_score(left, right)
    quantity_score = _quantity_score(left, right)
    pack_score = _pack_score(left, right)
    variant_score = _variant_score(left, right)
    title_similarity = token_set_ratio(left.title, right.title) / 100
    score = 0.0 if conflicts else round(0.40 * title_similarity + 0.23 * brand_score + 0.17 * quantity_score + 0.10 * pack_score + 0.10 * variant_score, 4)
    return MatchBreakdown(brand_score, quantity_score, pack_score, variant_score, round(title_similarity, 4), conflicts, score)


def score_match(left: ProductListing, right: ProductListing) -> float:
    return match_breakdown(left, right).final_confidence


def match_products(left_products: list[ProductListing], right_products: list[ProductListing], high_threshold: float = 0.85, min_threshold: float = 0.72) -> tuple[list[ProductMatch], list[ProductListing], list[ProductListing], int]:
    plausible = []
    for left_index, left in enumerate(left_products):
        for right_index, right in enumerate(right_products):
            if _hard_conflicts(left, right):
                continue
            breakdown = match_breakdown(left, right)
            plausible.append((breakdown.final_confidence, left_index, right_index, left, right, breakdown))
    candidates = [candidate for candidate in plausible if candidate[0] >= min_threshold]
    candidates.sort(reverse=True, key=lambda item: (item[0], -item[1], -item[2]))
    matches: list[ProductMatch] = []
    used_left: set[int] = set()
    used_right: set[int] = set()
    for score, left_index, right_index, left, right, breakdown in candidates:
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        matches.append(ProductMatch(left, right, score, "high" if score >= high_threshold else "medium", breakdown))
    unmatched_left = [left for index, left in enumerate(left_products) if index not in used_left]
    unmatched_right = [right for index, right in enumerate(right_products) if index not in used_right]
    return matches, unmatched_left, unmatched_right, len(plausible)
