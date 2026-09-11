import re
from dataclasses import dataclass

KNOWN_BRANDS = {
    "maggi", "amul", "britannia", "nestle", "cadbury", "haldiram",
    "parle", "mother dairy", "pepsi", "coca cola", "coke",
}

UNIT_PATTERN = re.compile(
    r"(?P<count>\d+)\s*[xX]\s*(?P<pack>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|g|gm|gram|grams|l|ltr|litre|liter|ml|pcs|pc|pieces)\b"
    r"|(?P<value>\d+(?:\.\d+)?)\s*(?P<single>kg|kgs|g|gm|gram|grams|l|ltr|litre|liter|ml|pcs|pc|pieces)\b",
    re.IGNORECASE,
)

@dataclass(frozen=True)
class QuantityInfo:
    total_value: float | None
    unit: str | None
    pack_count: int | None = None
    unit_value: float | None = None


def normalize_unit(unit: str) -> str:
    unit = unit.lower()
    if unit in {"kg", "kgs", "g", "gm", "gram", "grams"}:
        return "g"
    if unit in {"l", "ltr", "litre", "liter", "ml"}:
        return "ml"
    return "pcs"


def extract_quantity(text: str) -> QuantityInfo:
    match = UNIT_PATTERN.search(text)
    if not match:
        return QuantityInfo(None, None)
    if match.group("count"):
        count = int(match.group("count"))
        raw_value = float(match.group("pack"))
        raw_unit = match.group("unit")
    else:
        count = None
        raw_value = float(match.group("value"))
        raw_unit = match.group("single")
    unit = normalize_unit(raw_unit)
    if unit == "g" and raw_unit.lower() in {"kg", "kgs"}:
        raw_value *= 1000
    if unit == "ml" and raw_unit.lower() in {"l", "ltr", "litre", "liter"}:
        raw_value *= 1000
    return QuantityInfo(raw_value * (count or 1), unit, count, raw_value)


def normalize_text(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"\b(kg|kgs|g|gm|gram|grams|l|ltr|litre|liter|ml|pcs|pc|pieces)\b", " ", value)
    value = re.sub(r"\d+(?:\.\d+)?\s*[xX]\s*\d+(?:\.\d+)?", " ", value)
    value = re.sub(r"\d+(?:\.\d+)?", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\b(combo|offer|new pack)\b", " ", value)
    abbreviations = {"2 minute": "2 minute", "instant": "instant"}
    for source, target in abbreviations.items():
        value = value.replace(source, target)
    return " ".join(value.split())


def tokens(text: str) -> set[str]:
    return set(normalize_text(text).split())


def normalize_query(query: str) -> str:
    """Create a stable cache key component without changing the search meaning."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", query.lower().strip()).split())


def extract_brand(title: str, structured_brand: str | None = None) -> str | None:
    if structured_brand:
        return structured_brand.strip().lower()
    lowered = title.lower()
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(brand)}\b", lowered):
            return brand
    return None
