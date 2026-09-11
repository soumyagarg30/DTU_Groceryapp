import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path

from playwright.async_api import async_playwright
from ..core.config import settings
from .base import GroceryProvider, LocationContextError, ProviderSearchError
from ..models.product import ProductListing

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderContext:
    provider: str
    requested_location: str
    resolved_location: str | None
    location_verified: bool


class DesktopWebsiteProvider(GroceryProvider):
    """Browser provider base; concrete selectors remain isolated per provider."""

    homepage_url: str

    def __init__(self, name: str, timeout_ms: int = 8000, headless: bool | None = None, persistent_context: bool | None = None, browser_channel: str | None = None, manual_bootstrap: bool | None = None):
        self.name = name
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self.headless = settings.provider_headless if headless is None else headless
        self.persistent_context = settings.provider_use_persistent_context if persistent_context is None else persistent_context
        self.browser_channel = settings.provider_browser_channel if browser_channel is None else browser_channel
        self.manual_bootstrap = settings.provider_manual_bootstrap if manual_bootstrap is None else manual_bootstrap
        self.location_verified = False
        self.requested_location = None
        self.resolved_location = None

    @property
    def provider_context(self) -> ProviderContext:
        return ProviderContext(self.name, self.requested_location or "", self.resolved_location, self.location_verified)

    async def _page_for_session(self):
        if self._page:
            return self._page
        self._playwright = await async_playwright().start()
        context_options = {"viewport": {"width": 1440, "height": 900}, "locale": "en-IN", "timezone_id": "Asia/Kolkata"}
        if self.persistent_context:
            profile = Path(__file__).resolve().parents[2] / ".browser_profiles" / self.name
            profile.mkdir(parents=True, exist_ok=True)
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(str(profile), headless=self.headless, channel=self.browser_channel or None, **context_options)
            except Exception:
                self._context = await self._playwright.chromium.launch_persistent_context(str(profile), headless=self.headless, **context_options)
        else:
            try:
                self._browser = await self._playwright.chromium.launch(headless=self.headless, channel=self.browser_channel or None)
            except Exception:
                self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context(**context_options)
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        return self._page

    async def close(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def establish_location(self, location: str) -> None:
        if location != "DTU":
            raise LocationContextError("Only the configured DTU location is supported")
        page = await self._page_for_session()
        if getattr(page, "url", "") in ("", "about:blank"):
            await page.goto(self.homepage_url, wait_until="domcontentloaded")
        else:
            await page.wait_for_load_state("domcontentloaded")
        self.requested_location = location
        self.location_verified = False
        self.resolved_location = None
        await page.locator("body").wait_for(state="visible")
        page_text = (await page.locator("body").inner_text()).lower()
        self._check_login_required(page_text)
        if self._is_blocked_text(page_text):
            raise ProviderSearchError("blocked", f"{self.name} desktop website blocked automated access")
        self.resolved_location = await self._resolved_location_text(page)
        if not await self._verify_dtu_location(page):
            try:
                await self._set_dtu_location(page)
            except Exception:
                if not self.manual_bootstrap:
                    await self._capture_debug(page, "location_failure")
                    raise
                if self.headless:
                    raise LocationContextError("Manual bootstrap requires a headed browser")
                print("Please select Delhi Technological University / Shahbad Daulatpur as the delivery location in the browser.")
                print("Do not attempt to bypass any CAPTCHA or security challenge. Press Enter after the normal location flow is complete.")
                await asyncio.to_thread(input)
                await page.wait_for_load_state("domcontentloaded")
                body_text = (await page.locator("body").inner_text()).lower()
                if self._is_blocked_text(body_text):
                    raise ProviderSearchError("blocked", f"{self.name} desktop website blocked automated access")
        self.resolved_location = await self._resolved_location_text(page)
        self.location_verified = await self._verify_dtu_location(page)
        if not self.location_verified:
            await self._capture_debug(page, "location_failure")
            raise LocationContextError(f"{self.name} did not verify DTU delivery context")

    async def search(self, query: str, location: str) -> list[ProductListing]:
        if not self.location_verified:
            raise LocationContextError(f"{self.name} location was not verified before search")
        page = await self._page_for_session()
        return await self._search_visible_listings(page, query)

    async def _capture_debug(self, page, label: str) -> None:
        if not settings.provider_debug:
            return
        debug_dir = Path(__file__).resolve().parents[2] / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(debug_dir / f"{self.name}_{label}.png"), full_page=True)

    async def _set_dtu_location(self, page):
        raise NotImplementedError

    async def _verify_dtu_location(self, page) -> bool:
        resolved = (self.resolved_location or "").lower()
        return (
            "delhi technological university" in resolved
            or "shahbad daulatpur" in resolved
            or (("bawana road" in resolved or "bawana rd" in resolved) and ("dtu" in resolved or "technological university" in resolved))
        )

    @staticmethod
    def _check_login_required(text: str) -> None:
        normalized = " ".join(text.lower().split())
        # A normal header Login button is not a search access restriction.
        if any(message in normalized for message in (
            "please login to continue searching",
            "please log in to continue searching",
            "sign in to continue searching",
        )):
            raise ProviderSearchError("login_required", "Sign in to the provider browser to continue searching")

    @staticmethod
    def _is_blocked_text(text: str) -> bool:
        return any(marker in text for marker in ("request blocked", "access denied", "you have been blocked", "automated access", "captcha"))

    async def _resolved_location_text(self, page) -> str | None:
        return None

    async def _search_visible_listings(self, page, query: str) -> list[ProductListing]:
        raise NotImplementedError

    async def _wait_for_cards_or_empty(self, page, card_selectors: tuple[str, ...], empty_selectors: tuple[str, ...], timeout_ms: int = 15000):
        # Give all candidate selectors one shared deadline. Waiting 15 seconds
        # on each obsolete selector made a five-selector search take 75 seconds.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_ms / 1000
        while True:
            body_text = await page.locator("body").inner_text()
            self._check_login_required(body_text)
            if self._is_blocked_text(body_text.lower()):
                raise ProviderSearchError("blocked", f"{self.name} desktop website blocked automated access")
            for selector in card_selectors:
                cards = page.locator(selector)
                if await cards.count() and await cards.first.is_visible():
                    return cards
            for selector in empty_selectors:
                empty = page.locator(selector).first
                if await empty.count() and await empty.is_visible():
                    return None
            if loop.time() >= deadline:
                break
            await asyncio.sleep(min(0.15, max(0, deadline - loop.time())))
        body_text = (await page.locator("body").inner_text())
        await self._capture_debug(page, "search_failure")
        if self._is_blocked_text(body_text.lower()):
            raise ProviderSearchError("blocked", f"{self.name} desktop website blocked automated access")
        raise ProviderSearchError("selector_failure", f"{self.name} product cards were not found at {page.url}")
