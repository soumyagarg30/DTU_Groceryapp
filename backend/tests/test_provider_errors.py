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