"""One-time, normal-browser bootstrap for a provider's persistent DTU session."""

import argparse
import asyncio

from ..providers.blinkit import BlinkitProvider
from ..providers.zepto import ZeptoProvider
from .check_live_providers import check_provider


async def main(provider_name: str, query: str) -> None:
    provider_types = {"blinkit": BlinkitProvider, "zepto": ZeptoProvider}
    provider = provider_types[provider_name](provider_name, headless=False, persistent_context=True, manual_bootstrap=True)
    await check_provider(provider, query)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap a persistent provider session through its normal public website")
    parser.add_argument("provider", choices=("blinkit", "zepto"))
    parser.add_argument("--query", default="Maggi")
    args = parser.parse_args()
    asyncio.run(main(args.provider, args.query))
