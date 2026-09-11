import asyncio
import pytest
from app.providers.browser import DesktopWebsiteProvider
from app.services.search_service import SearchService


@pytest.mark.asyncio
async def test_fallback_selector_is_checked_without_waiting_for_first():
    class Locator:
        first = property(lambda self: self)
        def __init__(self, visible): self.visible = visible
        async def inner_text(self): return "Product results"
        async def count(self): return int(self.visible)
        async def is_visible(self): return self.visible
    class Page:
        def locator(self, selector): return Locator(selector == 'working')
    provider = DesktopWebsiteProvider('test')
    result = await asyncio.wait_for(provider._wait_for_cards_or_empty(Page(), ('obsolete', 'working'), (), 15000), timeout=0.5)
    assert await result.is_visible()


@pytest.mark.asyncio
async def test_identical_concurrent_queries_fetch_once():
    class Provider:
        location_verified = True
        calls = 0
        async def establish_location(self, location): pass
        async def search(self, query, location):
            self.calls += 1
            await asyncio.sleep(0.02)
            return []
    provider = Provider()
    service = SearchService({'blinkit': provider})
    results = await asyncio.gather(*(service.search('milk') for _ in range(5)))
    assert provider.calls == 1
    assert len(results) == 5
    await asyncio.sleep(0)
    assert not service.inflight
