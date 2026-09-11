import pytest
from app.providers.base import ProviderSearchError
from app.providers.browser import DesktopWebsiteProvider


class ProbeProvider(DesktopWebsiteProvider):
    homepage_url = "https://example.com"

    async def _set_dtu_location(self, page):
        raise AssertionError("blocked pages must fail before location interaction")

    async def _search_visible_listings(self, page, query):
        return []


@pytest.mark.asyncio
async def test_blocked_page_is_rejected_before_location_flow():
    provider = ProbeProvider("probe")

    class Body:
        async def wait_for(self, state):
            return None

        async def inner_text(self):
            return "Request Blocked: your request looks automated"

    class Page:
        async def goto(self, url, wait_until):
            return None

        def locator(self, selector):
            return Body()

    async def page_for_session():
        return Page()

    provider._page_for_session = page_for_session
    with pytest.raises(ProviderSearchError, match="blocked automated access"):
        await provider.establish_location("DTU")

@pytest.mark.asyncio
async def test_blinkit_returns_home_before_verifying_location(monkeypatch):
    from app.providers.blinkit import BlinkitProvider
    calls = []

    class Page:
        async def goto(self, url, wait_until):
            calls.append(('navigate', url))

    provider = BlinkitProvider('blinkit')

    async def page_for_session():
        return Page()

    async def verify(self, location):
        calls.append(('verify', location))
        assert self.location_verified is False

    provider._page_for_session = page_for_session
    monkeypatch.setattr(DesktopWebsiteProvider, 'establish_location', verify)
    provider.location_verified = True
    await provider.establish_location('DTU')
    assert calls == [('navigate', 'https://blinkit.com/'), ('verify', 'DTU')]


@pytest.mark.asyncio
async def test_simultaneous_searches_do_not_share_provider_tab():
    import asyncio
    from app.services.search_service import SearchService

    class Provider:
        location_verified = True
        busy = False

        async def establish_location(self, location):
            assert not self.busy
            self.busy = True
            await asyncio.sleep(0)

        async def search(self, query, location):
            assert self.busy
            await asyncio.sleep(0)
            self.busy = False
            return []

    service = SearchService({'blinkit': Provider()})
    responses = await asyncio.gather(service.search('milk'), service.search('bread'))
    assert all(r.provider_status['blinkit'] == 'empty' for r in responses)
