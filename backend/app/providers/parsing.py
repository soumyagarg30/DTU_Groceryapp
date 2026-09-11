import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import Locator

from ..models.product import ProductListing

INR_PATTERN = re.compile(r"(?:₹|Rs\.?|INR)\s*([0-9]+(?:\.[0-9]{1,2})?)", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])([0-9]+(?:\.[0-9]{1,2})?)(?![A-Za-z])")


def parse_inr_price(text: str | None) -> float | None:
    if not text:
        return None
    match = INR_PATTERN.search(text.replace(",", ""))
    return float(match.group(1)) if match else None


def parse_inr_prices(text: str | None) -> list[float]:
    if not text:
        return []
    return [float(value) for value in INR_PATTERN.findall(text.replace(",", ""))]


def parse_visible_prices(text: str | None) -> list[float]:
    prices = parse_inr_prices(text)
    if prices or not text:
        return prices
    numeric_lines = []
    for line in text.splitlines():
        candidate = line.strip().replace(",", "")
        if re.fullmatch(r"\d+(?:\.\d{1,2})?", candidate):
            numeric_lines.append(float(candidate))
    return numeric_lines[-2:]


def parse_first_number(text: str | None) -> float | None:
    if not text:
        return None
    match = NUMBER_PATTERN.search(text.replace(",", ""))
    return float(match.group(1)) if match else None


async def first_text(locator: Locator, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        candidate = locator.locator(selector).first
        if await candidate.count() and await candidate.is_visible():
            value = (await candidate.inner_text()).strip()
            if value:
                return value
    return None


async def first_attribute(locator: Locator, selectors: tuple[str, ...], attribute: str) -> str | None:
    for selector in selectors:
        candidate = locator.locator(selector).first
        if await candidate.count():
            value = await candidate.get_attribute(attribute)
            if value:
                return value
    return None


async def listing_from_card(card: Locator, provider: str, base_url: str, title_selectors: tuple[str, ...], price_selectors: tuple[str, ...], mrp_selectors: tuple[str, ...], quantity_selectors: tuple[str, ...]) -> ProductListing | None:
    card_text = await card.inner_text()
    title = await first_text(card, title_selectors)
    lines = [line.strip() for line in card_text.splitlines() if line.strip()]
    if not title:
        title_candidates = [line for line in lines if "₹" not in line and "ADD" not in line.upper() and "OFF" not in line.upper() and not re.search(r"\b\d+(?:\.\d+)?\s*(?:g|kg|ml|l|pcs)\b", line, re.IGNORECASE) and not re.search(r"\b\d+\s*mins?\b", line, re.IGNORECASE)]
        title = max(title_candidates, key=len, default=None)
    if not title:
        return None
    price_text = await first_text(card, price_selectors) or card_text
    prices = parse_visible_prices(price_text)
    price = prices[0] if prices else parse_inr_price(price_text)
    if price is None:
        return None
    mrp = parse_inr_price(await first_text(card, mrp_selectors))
    if mrp is None and len(prices) > 1:
        mrp = prices[1]
    quantity_text = await first_text(card, quantity_selectors)
    if not quantity_text:
        quantity_text = next((line for line in lines if re.search(r"\b\d+(?:\.\d+)?\s*(?:g|kg|ml|l|pcs|piece|pieces)\b", line, re.IGNORECASE) or re.search(r"\b\d+\s*x\s*\d+", line, re.IGNORECASE)), None)
    href = await first_attribute(card, ("a[href]",), "href")
    image_url = await first_attribute(card, ("img[src]", "img[data-src]"), "src") or await first_attribute(card, ("img[data-src]",), "data-src")
    unavailable_text = card_text.lower()
    available = not any(marker in unavailable_text for marker in ("out of stock", "unavailable", "sold out"))
    return ProductListing(
        provider=provider,
        external_id=href,
        title=title,
        price=price,
        mrp=mrp if mrp != price else None,
        quantity_text=quantity_text,
        available=available,
        product_url=urljoin(base_url, href) if href else None,
        image_url=urljoin(base_url, image_url) if image_url else None,
        raw_title=title,
        raw_card_text=card_text[:1000],
        fetched_at=datetime.now(timezone.utc),
        metadata={"card_text": card_text[:500]},
    )
