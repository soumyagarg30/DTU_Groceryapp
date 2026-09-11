import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.config import settings
from ..models.product import ProductListing
from ..models.search import CacheMetadata, ComparisonResult, MatchDetails, PipelineMetadata, PublicListing, Quantity, SearchResponse
from ..providers.base import GroceryProvider
from ..providers.base import LocationContextError, ProviderSearchError
from ..services.matcher import match_products
from ..services.normalization import extract_brand, extract_quantity, normalize_query
from ..services.result_pipeline import deduplicate_listings, pipeline_counts, product_family, rank_by_query_relevance
from ..services.pricing import calculate_savings_percentage, calculate_unit_price

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    normalized_query: str
    location: str
    fetched_at: datetime
    expires_at: float
    value: SearchResponse
    # The cache miss that populated this entry is itself one query request.
    hit_count: int = 1
    last_accessed_at: float = 0.0


class HotQueryCache:
    def __init__(self, max_entries: int = 20, ttl_seconds: int = settings.cache_ttl_seconds, clock=time.monotonic):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self.entries: OrderedDict[tuple[str, str], CacheEntry] = OrderedDict()

    @staticmethod
    def key(query: str, location: str) -> tuple[str, str]:
        return normalize_query(query), location.strip().lower()

    def clear_expired(self) -> None:
        now = self.clock()
        for key, entry in list(self.entries.items()):
            if entry.expires_at <= now:
                del self.entries[key]

    def get(self, query: str, location: str) -> tuple[SearchResponse, CacheEntry] | None:
        self.clear_expired()
        entry = self.entries.get(self.key(query, location))
        if entry is None:
            return None
        entry.hit_count += 1
        entry.last_accessed_at = self.clock()
        self.entries.move_to_end(self.key(query, location))
        age_seconds = max(0, int((datetime.now(timezone.utc) - entry.fetched_at).total_seconds()))
        value = entry.value.model_copy(update={"cache": CacheMetadata(hit=True, age_seconds=age_seconds, fetched_at=entry.fetched_at)})
        return value, entry

    def put(self, query: str, location: str, value: SearchResponse) -> None:
        self.clear_expired()
        normalized_query = normalize_query(query)
        now = self.clock()
        fetched_at = value.cache.fetched_at
        key = self.key(query, location)
        self.entries[key] = CacheEntry(normalized_query, location, fetched_at, now + self.ttl_seconds, value, last_accessed_at=now)
        self.entries.move_to_end(key)
        self.evict_if_needed()

    def evict_if_needed(self) -> None:
        while len(self.entries) > self.max_entries:
            coldest_key = min(self.entries, key=lambda key: (self.entries[key].hit_count, self.entries[key].last_accessed_at))
            del self.entries[coldest_key]

    def hottest(self, limit: int = 8) -> list[dict[str, int | str]]:
        self.clear_expired()
        ranked = sorted(self.entries.values(), key=lambda entry: (-entry.hit_count, -entry.last_accessed_at, entry.normalized_query))
        return [{"query": entry.normalized_query, "hit_count": entry.hit_count} for entry in ranked[:max(0, min(limit, 8))]]


class SearchService:
    def __init__(self, providers: dict[str, GroceryProvider], cache_ttl_seconds: int = settings.cache_ttl_seconds, cache: HotQueryCache | None = None):
        self.providers = providers
        self.cache = cache or HotQueryCache(ttl_seconds=cache_ttl_seconds)
        self.provider_locks = {name: asyncio.Lock() for name in providers}

    async def search(self, query: str, location: str = "DTU") -> SearchResponse:
        cleaned_query = query.strip()
        if not 2 <= len(cleaned_query) <= 100:
            raise ValueError("Search query must be between 2 and 100 characters")
        if location != "DTU":
            raise ValueError("Only DTU delivery is supported")
        cached = self.cache.get(cleaned_query, location)
        if cached:
            return cached[0]

        async def run_provider(name: str, provider: GroceryProvider):
            # A provider owns one browser tab; location and search are atomic.
            async with self.provider_locks[name]:
                return await run_provider_locked(name, provider)

        async def run_provider_locked(name: str, provider: GroceryProvider):
            started = time.monotonic()
            try:
                await provider.establish_location(location)
                if getattr(provider, "location_verified", True) is not True:
                    raise LocationContextError(f"{name} did not verify DTU delivery context")
                listings = await provider.search(cleaned_query, location)
                logger.info("provider_search query=%s provider=%s duration_ms=%d products=%d", cleaned_query, name, (time.monotonic() - started) * 1000, len(listings))
                return name, listings, "ok", ""
            except ProviderSearchError as error:
                logger.warning("provider_failure query=%s provider=%s duration_ms=%d reason=%s", cleaned_query, name, (time.monotonic() - started) * 1000, error.code)
                return name, [], "unavailable", error.code
            except Exception as error:
                logger.exception("provider_failure query=%s provider=%s duration_ms=%d error=%s", cleaned_query, name, (time.monotonic() - started) * 1000, type(error).__name__)
                return name, [], "unavailable", "Provider could not verify DTU delivery context or complete the search."

        provider_results = await asyncio.gather(*(run_provider(name, provider) for name, provider in self.providers.items()))
        by_name = {name: (listings, status, message) for name, listings, status, message in provider_results}
        blinkit, blinkit_status, blinkit_message = by_name.get("blinkit", ([], "unavailable", "Provider not configured"))
        zepto, zepto_status, zepto_message = by_name.get("zepto", ([], "unavailable", "Provider not configured"))
        raw_counts = {"blinkit": len(blinkit), "zepto": len(zepto)}
        blinkit = rank_by_query_relevance(deduplicate_listings(blinkit), cleaned_query)
        zepto = rank_by_query_relevance(deduplicate_listings(zepto), cleaned_query)
        deduplicated_counts = {"blinkit": len(blinkit), "zepto": len(zepto)}
        matches, unmatched_blinkit, unmatched_zepto, candidate_pairs = match_products(blinkit, zepto, settings.match_high_threshold, settings.match_min_threshold)
        response_results = [self._comparison(match.left, match.right, match.score, match.confidence, match.breakdown) for match in matches]
        # Unmatched products are useful only when they are still strongly related
        # to the user's query; otherwise provider recommendation carousels leak
        # unrelated bread/snack cards into the final Top-K.
        response_results.extend(self._unmatched(listing, "blinkit") for listing in unmatched_blinkit if listing.metadata.get("query_relevance_score", 0) >= 0.25)
        response_results.extend(self._unmatched(listing, "zepto") for listing in unmatched_zepto if listing.metadata.get("query_relevance_score", 0) >= 0.25)
        response_results.sort(key=lambda result: (result.match_confidence == "unmatched", result.match_confidence != "high", -(result.match_score or result.query_relevance_score or 0), -(result.query_relevance_score or 0)))
        response_results = response_results[:settings.top_k_results]
        response = SearchResponse(
            query=cleaned_query,
            location="DTU",
            demo_mode=settings.use_mock_providers,
            results=response_results,
            provider_status={"blinkit": blinkit_status if blinkit else ("empty" if blinkit_status == "ok" else blinkit_status), "zepto": zepto_status if zepto else ("empty" if zepto_status == "ok" else zepto_status)},
            provider_messages={name: message for name, message in (("blinkit", blinkit_message), ("zepto", zepto_message)) if message},
            cache=CacheMetadata(hit=False, age_seconds=0, fetched_at=datetime.now(timezone.utc)),
            pipeline=PipelineMetadata(**pipeline_counts(raw_counts, deduplicated_counts, candidate_pairs, len(matches), len(response_results))),
        )
        if blinkit_status != "unavailable" or zepto_status != "unavailable":
            self.cache.put(cleaned_query, location, response)
        return response

    @staticmethod
    def _public(listing: ProductListing) -> PublicListing:
        unit_price = calculate_unit_price(listing)
        return PublicListing(title=listing.title, price=listing.price, mrp=listing.mrp, currency=listing.currency, quantity_text=listing.quantity_text, available=listing.available, product_url=listing.product_url, source=listing.provider, unit_price=unit_price.unit_price if unit_price else None, unit_price_basis=unit_price.unit_price_basis if unit_price else None)

    def _comparison(self, blinkit: ProductListing, zepto: ProductListing, score: float, confidence: str, breakdown) -> ComparisonResult:
        comparable = score >= settings.match_high_threshold and blinkit.available and zepto.available
        cheaper = None
        difference = None
        savings_percentage = None
        if comparable:
            cheaper = "same_price" if blinkit.price == zepto.price else ("blinkit" if blinkit.price < zepto.price else "zepto")
            difference = round(abs(blinkit.price - zepto.price), 2)
            savings_percentage = calculate_savings_percentage(blinkit.price, zepto.price)
        quantity = extract_quantity(blinkit.quantity_text or blinkit.title)
        matched_brand = blinkit.brand or extract_brand(blinkit.title)
        reasons = [f"Same brand: {matched_brand.title()}"] if matched_brand and matched_brand.lower() == (zepto.brand or extract_brand(zepto.title) or "").lower() else []
        if quantity.total_value is not None and quantity.total_value == extract_quantity(zepto.quantity_text or zepto.title).total_value:
            reasons.append(f"Same quantity: {quantity.total_value:g} {quantity.unit}")
        if breakdown.pack_score == 1:
            reasons.append("Same pack structure")
        if breakdown.variant_score == 1:
            reasons.append("Same variant")
        if product_family(blinkit.title) and product_family(blinkit.title) == product_family(zepto.title):
            reasons.append("Same product family")
        if breakdown.title_similarity >= 0.75:
            reasons.append("Strong title similarity")
        relevance = round(max(blinkit.metadata.get("query_relevance_score", 0), zepto.metadata.get("query_relevance_score", 0)), 4)
        details = MatchDetails(brand_score=breakdown.brand_score, quantity_score=breakdown.quantity_score, pack_score=breakdown.pack_score, variant_score=breakdown.variant_score, title_similarity=breakdown.title_similarity, conflicts=list(breakdown.conflicts))
        return ComparisonResult(match_id=hashlib.sha1(f"{blinkit.external_id or blinkit.title}:{zepto.external_id or zepto.title}".encode()).hexdigest()[:12], canonical_name=blinkit.title, brand=blinkit.brand or extract_brand(blinkit.title), quantity=Quantity(value=quantity.total_value, unit=quantity.unit), match_score=score, match_confidence=confidence, blinkit=self._public(blinkit), zepto=self._public(zepto), cheaper_provider=cheaper, price_difference=difference, savings_percentage=savings_percentage, query_relevance_score=relevance, match_reasons=reasons, match_details=details)

    def _unmatched(self, listing: ProductListing, provider: str) -> ComparisonResult:
        quantity = extract_quantity(listing.quantity_text or listing.title)
        public_listing = self._public(listing)
        return ComparisonResult(match_id=hashlib.sha1(f"{listing.external_id or listing.title}:{provider}".encode()).hexdigest()[:12], canonical_name=listing.title, brand=listing.brand or extract_brand(listing.title), quantity=Quantity(value=quantity.total_value, unit=quantity.unit), match_confidence="unmatched", query_relevance_score=listing.metadata.get("query_relevance_score"), **{provider: public_listing})


def create_search_service() -> SearchService:
    if settings.use_mock_providers:
        from ..providers.mock import MockProvider
        providers: dict[str, GroceryProvider] = {"blinkit": MockProvider("blinkit"), "zepto": MockProvider("zepto")}
    else:
        from ..providers.blinkit import BlinkitProvider
        from ..providers.zepto import ZeptoProvider
        providers = {"blinkit": BlinkitProvider("blinkit", int(settings.request_timeout_seconds * 1000)), "zepto": ZeptoProvider("zepto", int(settings.request_timeout_seconds * 1000))}
    return SearchService(providers, cache=HotQueryCache(max_entries=settings.hot_query_cache_max_entries, ttl_seconds=settings.cache_ttl_seconds))
