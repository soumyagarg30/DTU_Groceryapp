import argparse
import asyncio

from ..providers.base import LocationContextError, ProviderSearchError
from ..providers.blinkit import BlinkitProvider
from ..providers.zepto import ZeptoProvider


async def check_provider(provider, query: str) -> None:
    print(provider.name.title())
    print(f"Browser mode: {'headed' if not provider.headless else 'headless'}")
    try:
        await provider.establish_location("DTU")
        print(f"Location verified: {provider.location_verified}")
        print(f"Resolved location: {provider.resolved_location or 'unknown'}")
        listings = await provider.search(query, "DTU")
        print(f"Search URL/state: {provider._page.url}")
        print(f"Products: {len(listings)}")
        for index, listing in enumerate(listings[:3], start=1):
            print(f"{index}. {listing.title}")
            print(f"₹{listing.price:g}")
            print(listing.quantity_text or "quantity unavailable")
        if len(listings) > 3:
            print(f"... {len(listings) - 3} more extracted listings")
    except LocationContextError as error:
        print("Location verified: false")
        print(f"Provider unavailable: {error}")
    except ProviderSearchError as error:
        print(f"Location verified: {provider.location_verified}")
        print(f"Resolved location: {provider.resolved_location or 'unknown'}")
        print(f"Provider {error.code}: {error}")
    except Exception as error:
        print(f"Provider unavailable: {type(error).__name__}: {error}")
    finally:
        await provider.close()


async def main(query: str, selected_provider: str | None, headed: bool, manual_bootstrap: bool) -> None:
    provider_types = {"blinkit": BlinkitProvider, "zepto": ZeptoProvider}
    names = [selected_provider] if selected_provider else list(provider_types)
    for name in names:
        provider = provider_types[name](name, headless=not headed, manual_bootstrap=manual_bootstrap)
        await check_provider(provider, query)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Opt-in live DTU provider check")
    parser.add_argument("query", nargs="?", default="Maggi")
    parser.add_argument("--headed", action="store_true", help="Use a visible browser")
    parser.add_argument("--provider", choices=("blinkit", "zepto"), help="Check one provider")
    parser.add_argument("--manual-bootstrap", action="store_true", help="Allow manual DTU selection in the visible browser")
    args = parser.parse_args()
    asyncio.run(main(args.query, args.provider, args.headed, args.manual_bootstrap))
