import re

from .base import ProviderSearchError
from .browser import DesktopWebsiteProvider
from .parsing import listing_from_card


class BlinkitProvider(DesktopWebsiteProvider):
    homepage_url = "https://blinkit.com/"
    location_triggers = ("text=Select Location", "button:has-text('Delivery location')", "button:has-text('Select location')", "[aria-label*='location' i]")
    location_inputs = ("input[placeholder*='delivery location' i]", "input[placeholder*='search location' i]", "input[aria-label*='location' i]")
    search_inputs = ("input[placeholder*='Search for products' i]", "input[placeholder*='Search' i]")
    card_selectors = ("button:has-text('ADD')", "[data-testid*='product' i]", "[data-test*='product' i]", "a[href*='/prn/']", "div[role='article']")

    async def establish_location(self, location: str) -> None:
        # Blinkit's search layout hides the delivery header. Re-open the home
        # layout before verification instead of mistaking a hidden header for
        # a lost delivery context. The base class still verifies DTU afresh.
        if location == "DTU":
            page = await self._page_for_session()
            self.location_verified = False
            self.resolved_location = None
            await page.goto(self.homepage_url, wait_until="domcontentloaded")
        await super().establish_location(location)

    async def _set_dtu_location(self, page):
        continue_web = page.get_by_text("Continue on web", exact=True)
        if await continue_web.count() and await continue_web.is_visible():
            await continue_web.click()
            await page.wait_for_timeout(500)
        location_field = None
        for selector in self.location_inputs:
            candidate = page.locator(selector).first
            if await candidate.count() and await candidate.is_visible():
                location_field = candidate
                break
        if location_field is None:
            for selector in self.location_triggers:
                trigger = page.locator(selector).first
                if await trigger.count() and await trigger.is_visible():
                    await trigger.click()
                    await page.wait_for_timeout(500)
                    break
            manual = page.get_by_text("Select manually", exact=True)
            if await manual.count() and await manual.is_visible():
                await manual.click()
                await page.wait_for_timeout(500)
            for selector in self.location_inputs:
                candidate = page.locator(selector).first
                if await candidate.count() and await candidate.is_visible():
                    location_field = candidate
                    break
        if location_field is None:
            raise RuntimeError("Blinkit location input was not found")
        await location_field.fill("Delhi Technological University, Shahbad Daulatpur, Delhi")
        suggestion = page.get_by_text("Delhi Technological University", exact=True).first
        await suggestion.wait_for(state="visible")
        await suggestion.click()
        await page.wait_for_timeout(1000)

    async def _resolved_location_text(self, page) -> str | None:
        for selector in ("[aria-label*='location' i]", "button:has-text('Delhi')", "header"):
            candidate = page.locator(selector).first
            if await candidate.count() and await candidate.is_visible():
                text = (await candidate.inner_text()).strip()
                if "delhi technological university" in text.lower() or "shahbad daulatpur" in text.lower():
                    return text
        return None

    async def _search_visible_listings(self, page, query: str):
        field = None
        for selector in self.search_inputs:
            candidate = page.locator(selector).first
            if await candidate.count() and await candidate.is_visible():
                field = candidate
                break
        if field is None:
            search_link = page.locator("a[href='/s/']").first
            if not await search_link.count() or not await search_link.is_visible():
                search_link = page.get_by_text("Search", exact=False).first
            if await search_link.count() and await search_link.is_visible():
                await search_link.click()
                await page.wait_for_timeout(500)
                await page.wait_for_load_state("domcontentloaded")
                for selector in self.search_inputs + ("input[placeholder*='atta dal' i]",):
                    candidate = page.locator(selector).first
                    if await candidate.count() and await candidate.is_visible():
                        field = candidate
                        break
        if field is not None:
            await field.fill(query)
        else:
            raise RuntimeError("Blinkit search input was not found")
        await page.keyboard.press("Enter")
        try:
            await page.get_by_text(f'Showing results for "{query.lower()}"', exact=False).wait_for(state="visible", timeout=15000)
        except Exception:
            pass
        add_control = page.get_by_role("button", name=re.compile(r"ADD", re.IGNORECASE))
        if await add_control.count():
            await add_control.first.wait_for(state="visible", timeout=15000)
            cards = add_control
        else:
            cards = await self._wait_for_cards_or_empty(page, self.card_selectors, ("text=No products", "text=No results"))
        if cards is None:
            return []
        listings = []
        for index in range(min(await cards.count(), 200)):
            listing = await listing_from_card(cards.nth(index), "blinkit", self.homepage_url, ("[data-testid*='name' i]", "h3", "h2", "a[href*='/prn/']"), ("[data-testid*='price' i]", "[class*='price' i]"), ("del", "[data-testid*='mrp' i]"), ("[data-testid*='quantity' i]", "[class*='quantity' i]"))
            if listing:
                listings.append(listing)
        if not listings:
            sample = (await cards.first.inner_text())[:300].replace("\n", " ") if await cards.count() else "none"
            raise ProviderSearchError("extraction_failure", f"Blinkit cards were visible but fields could not be extracted sample={sample}")
        return listings
