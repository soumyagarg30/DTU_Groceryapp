import re

from .base import ProviderSearchError
from .browser import DesktopWebsiteProvider
from .parsing import listings_from_cards


class ZeptoProvider(DesktopWebsiteProvider):
    """Zepto's normal public desktop flow; no private API or token replay."""

    homepage_url = "https://www.zepto.com/"
    location_triggers = (
        "button:has-text('Select Location')",
        "[role='button']:has-text('Select Location')",
        "button:has-text('Add location')",
        "[aria-label*='location' i]",
    )
    location_inputs = (
        "input[placeholder*='Search a new address' i]",
        "input[placeholder*='Search for an area' i]",
        "input[placeholder*='Search location' i]",
        "input[placeholder*='address' i]",
        "input[aria-label*='location' i]",
    )
    search_inputs = (
        "input[placeholder*='Search for over' i]",
        "input[placeholder*='Search for products' i]",
        "input[aria-label*='search' i]",
    )
    card_selectors = (
        "[data-testid*='product-card' i]",
        "[data-testid*='product' i]",
        "article:has(button:has-text('ADD'))",
        "a[href*='/pn/']",
        "a[href*='/pvid/']",
    )

    async def _set_dtu_location(self, page):
        field = await self._visible_first(page, self.location_inputs)
        if field is None:
            trigger = await self._visible_first(page, self.location_triggers)
            if trigger is not None:
                await trigger.click()
                await page.wait_for_timeout(600)
            field = await self._visible_first(page, self.location_inputs)
        if field is None:
            raise RuntimeError("Zepto location input was not found")

        await field.fill("Delhi Technological University, Shahbad Daulatpur")
        suggestion = page.get_by_text(re.compile(r"Delhi Technological University|Shahbad Daulatpur", re.IGNORECASE)).first
        await suggestion.wait_for(state="visible")
        await suggestion.click()
        await page.wait_for_timeout(1200)

    async def _resolved_location_text(self, page) -> str | None:
        selectors = (
            "[data-testid*='location' i]",
            "button[aria-label*='location' i]",
            "[role='button']:has-text('Shahbad')",
            "[role='button']:has-text('Bawana')",
            "header",
        )
        for selector in selectors:
            candidate = page.locator(selector).first
            if await candidate.count() and await candidate.is_visible():
                text = (await candidate.inner_text()).strip()
                lowered = text.lower()
                if "delhi technological university" in lowered or "shahbad daulatpur" in lowered or (("bawana road" in lowered or "bawana rd" in lowered) and ("dtu" in lowered or "technological university" in lowered)):
                    return text
        return None

    async def _search_visible_listings(self, page, query: str):
        field = await self._visible_first(page, self.search_inputs)
        if field is None:
            search_link = page.locator("a[href='/search'], a[href*='/search']").first
            if await search_link.count() and await search_link.is_visible():
                await search_link.click()
                await page.wait_for_timeout(600)
            field = await self._visible_first(page, self.search_inputs)
        if field is None:
            raise RuntimeError("Zepto search input was not found")

        await field.fill(query)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)
        cards = await self._wait_for_cards_or_empty(page, self.card_selectors, ("text=No products", "text=No results", "text=We couldn't find"))
        if cards is None:
            return []

        listings = await listings_from_cards(
                cards,
                "zepto",
                self.homepage_url,
                ("[data-testid*='name' i]", "h3", "h2", "h4", "[title]"),
                ("[data-testid*='price' i]", "[class*='price' i]"),
                ("del", "s", "[data-testid*='mrp' i]"),
                ("[data-testid*='quantity' i]", "[class*='quantity' i]", "[class*='weight' i]"),
            )
        if not listings:
            raise ProviderSearchError("extraction_failure", "Zepto cards were visible but product fields could not be extracted")
        return listings

    @staticmethod
    async def _visible_first(page, selectors):
        for selector in selectors:
            candidate = page.locator(selector).first
            if await candidate.count() and await candidate.is_visible():
                return candidate
        return None
