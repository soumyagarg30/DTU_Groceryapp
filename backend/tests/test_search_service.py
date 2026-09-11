import pytest
from app.models.product import ProductListing
from app.providers.base import GroceryProvider, LocationContextError
from app.services.search_service import HotQueryCache, SearchService


class WorkingProvider(GroceryProvider):
    def __init__(self, name):
        self.name = name
        self.search_calls = 0

    async def establish_location(self, location):
        assert location == "DTU"

    async def search(self, query, location):
        self.search_calls += 1
        return [ProductListing(provider=self.name, title="Maggi Masala Noodles 280g", brand="Maggi", price=58, quantity_text="280g", available=True)]


class FailingLocationProvider(WorkingProvider):
    async def establish_location(self, location):
        raise LocationContextError("DTU could not be verified")


class UnverifiedProvider(WorkingProvider):
    location_verified = False


@pytest.mark.asyncio
async def test_unverified_provider_is_unavailable_but_other_provider_survives():
    service = SearchService({"blinkit": WorkingProvider("blinkit"), "zepto": FailingLocationProvider("zepto")}, cache_ttl_seconds=0)
    response = await service.search("maggi")
    assert response.provider_status == {"blinkit": "ok", "zepto": "unavailable"}
    assert len(response.results) == 1
    assert response.results[0].blinkit is not None
    assert response.results[0].zepto is None
    cached_response = next(iter(service.cache.entries.values())).value
    assert cached_response.provider_status["zepto"] == "unavailable"
    assert all(result.zepto is None for result in cached_response.results)


@pytest.mark.asyncio
async def test_explicitly_unverified_provider_prices_are_discarded():
    service = SearchService({"blinkit": WorkingProvider("blinkit"), "zepto": UnverifiedProvider("zepto")}, cache_ttl_seconds=180)
    response = await service.search("maggi")
    assert response.provider_status["zepto"] == "unavailable"
    assert all(result.zepto is None for result in response.results)
    assert all(result.cheaper_provider is None for result in response.results)


@pytest.mark.asyncio
async def test_fresh_cache_hit_avoids_provider_invocation():
    blinkit = WorkingProvider("blinkit")
    zepto = WorkingProvider("zepto")
    service = SearchService({"blinkit": blinkit, "zepto": zepto}, cache_ttl_seconds=180)
    first = await service.search(" Maggi ")
    second = await service.search("maggi")
    assert first.cache.hit is False
    assert second.cache.hit is True
    assert blinkit.search_calls == 1
    assert zepto.search_calls == 1


@pytest.mark.asyncio
async def test_expired_cache_entry_triggers_fresh_provider_calls():
    now = [0.0]
    cache = HotQueryCache(max_entries=20, ttl_seconds=10, clock=lambda: now[0])
    blinkit = WorkingProvider("blinkit")
    zepto = WorkingProvider("zepto")
    service = SearchService({"blinkit": blinkit, "zepto": zepto}, cache=cache)
    await service.search("maggi")
    now[0] = 11.0
    refreshed = await service.search("maggi")
    assert refreshed.cache.hit is False
    assert blinkit.search_calls == 2
    assert zepto.search_calls == 2


def test_cache_is_bounded_and_frequently_used_entries_survive_eviction():
    now = [0.0]
    cache = HotQueryCache(max_entries=20, ttl_seconds=180, clock=lambda: now[0])
    from app.models.search import CacheMetadata, SearchResponse
    from datetime import datetime, timezone

    def response(query):
        return SearchResponse(query=query, location="DTU", results=[], provider_status={"blinkit": "empty", "zepto": "empty"}, cache=CacheMetadata(hit=False, age_seconds=0, fetched_at=datetime.now(timezone.utc)))

    for index in range(20):
        cache.put(f"query-{index}", "DTU", response(f"query-{index}"))
    for _ in range(3):
        cache.get("query-0", "DTU")
    cache.put("query-20", "DTU", response("query-20"))
    assert len(cache.entries) == 20
    assert ("query 0", "dtu") in cache.entries


def test_lfu_uses_oldest_access_as_tie_breaker():
    from app.models.search import CacheMetadata, SearchResponse
    from datetime import datetime, timezone

    now = [0.0]
    cache = HotQueryCache(max_entries=2, ttl_seconds=180, clock=lambda: now[0])

    def response(query):
        return SearchResponse(query=query, location="DTU", results=[], provider_status={"blinkit": "empty", "zepto": "empty"}, cache=CacheMetadata(hit=False, age_seconds=0, fetched_at=datetime.now(timezone.utc)))

    cache.put("milk", "DTU", response("milk"))
    now[0] = 1.0
    cache.put("bread", "DTU", response("bread"))
    now[0] = 2.0
    cache.put("eggs", "DTU", response("eggs"))

    assert ("milk", "dtu") not in cache.entries
    assert ("bread", "dtu") in cache.entries
    assert ("eggs", "dtu") in cache.entries


def test_hot_queries_are_lfu_ordered_and_do_not_expose_values():
    from app.models.search import CacheMetadata, SearchResponse
    from datetime import datetime, timezone

    cache = HotQueryCache(max_entries=20, ttl_seconds=180)
    def response(query):
        return SearchResponse(query=query, location="DTU", results=[], provider_status={"blinkit": "empty", "zepto": "empty"}, cache=CacheMetadata(hit=False, age_seconds=0, fetched_at=datetime.now(timezone.utc)))
    cache.put("milk", "DTU", response("milk"))
    cache.put("maggi", "DTU", response("maggi"))
    cache.get("maggi", "DTU")
    cache.get("maggi", "DTU")
    cache.get("milk", "DTU")

    assert cache.hottest() == [{"query": "maggi", "hit_count": 3}, {"query": "milk", "hit_count": 2}]


def test_cache_keys_isolate_queries_and_locations():
    cache = HotQueryCache(max_entries=20, ttl_seconds=180)
    from app.models.search import CacheMetadata, SearchResponse
    from datetime import datetime, timezone
    value = SearchResponse(query="maggi", location="DTU", results=[], provider_status={"blinkit": "empty", "zepto": "empty"}, cache=CacheMetadata(hit=False, age_seconds=0, fetched_at=datetime.now(timezone.utc)))
    cache.put("Maggi", "DTU", value)
    cache.put("Butter", "DTU", value)
    cache.put("Maggi", "Other", value)
    assert len(cache.entries) == 3
    assert cache.get("maggi", "DTU") is not None
    assert cache.get("butter", "DTU") is not None
    assert cache.get("maggi", "Other") is not None
