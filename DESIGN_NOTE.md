# Design Note

## Architecture
React calls one FastAPI search endpoint. FastAPI coordinates two provider adapters. Each adapter first establishes and verifies the DTU delivery context through the provider's normal desktop website flow, then extracts visible listings. Results become a provider-independent `ProductListing`, pass through normalization and entity resolution, and return as comparison-ready data. A bounded in-memory hot-query cache stores only successful DTU-verified results, keyed by normalized query and location, with short TTL and LFU/LRU-style eviction.

## Why This Design
Provider adapters isolate fragile website selectors and location/session behavior. A deterministic matcher is easier to test, explain, and debug than an LLM. The service stays stateless except for bounded process-local caching, and `asyncio.gather` keeps independent provider latency from becoming serial.

## Product Identity
Entity resolution is the main challenge because the two catalogues use inconsistent titles, bundles, brands, and pack descriptions. Known brands and structured brand fields are preferred. Quantities normalize to grams, millilitres, or pieces. Hard rules reject known-brand conflicts, large quantity differences, incompatible variants, and suspicious pack-count differences. Remaining candidates score 45% title tokens, 25% brand, 20% quantity, and 10% variants. Only scores at least 0.72 are paired; at least 0.85 is high confidence, and the frontend explains the confidence basis.

Broad searches are reduced before matching: provider-local deduplication, query relevance ranking, family/unit/quantity candidate blocking, global one-to-one assignment, and a configurable Top-K cap. The response includes raw, deduplicated, candidate, matched, and returned counts for inspection without exposing provider parsing details in the UI.

## Provider Limitations
Verified DTU context is a prerequisite for accepting prices. Public grocery sites may change their DOM or block automated browsers. The adapters detect blocked/security pages and return provider failure rather than bypassing controls, attempting CAPTCHA workarounds, or using generic-location data. This preserves correctness at the cost of partial results.

## Where Matching Breaks
Bundles, promotions, and `4 x 70 g` versus a single `280 g` pack can be ambiguous. Provider titles can omit brand, quantity, or variant information. The system prefers a false negative over an obviously incorrect comparison. A provider that cannot verify DTU is unavailable rather than silently returning generic or stale location data.

## Scaling
For many locations, move DTU into a location abstraction with provider-specific address IDs, verified-location metadata, and cache keys of provider plus location plus query. For many users, replace the process-local cache with Redis, add throttling, metrics, retries, and structured logs, and consider a periodically refreshed normalized catalogue while retaining live location verification for price/availability.
