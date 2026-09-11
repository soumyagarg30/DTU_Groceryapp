# DTU Grocery Price Compare

## Overview
DTU Grocery Price Compare compares grocery listings from Blinkit and Zepto for delivery to Delhi Technological University, Shahbad Daulatpur, Delhi. It uses provider adapters, deterministic normalization, and conservative product matching so a provider cannot contribute prices until its DTU delivery context is established and verified.

## Architecture
```text
React + Vite
    |
    v
FastAPI search endpoint
    |
    v
Provider adapters: location flow -> visible search results
    |
    v
Provider-independent ProductListing
    |
    v
Normalization -> quantity/brand/variant extraction
    |
    v
Deterministic product matcher
    |
    v
Comparison response
```

The live flow is: open the normal desktop website, open its location control, select a DTU/Shahbad Daulatpur result, verify the resolved location text, then search and read visible product cards. The provider boundary explicitly requires `establish_location("DTU")` before `search()`. Selectors and parsing stay isolated inside each adapter. If DTU cannot be verified, or the site blocks automation, that provider is returned as unavailable and no prices from that session are used. Security controls are never bypassed.

For a deterministic demo, set `USE_MOCK_PROVIDERS=true` in `backend/.env`, start the backend, and use the frontend. The UI displays **Demo data** and those fixture prices are never described as live. For live mode, leave it `false`, install Chromium with `playwright install chromium`, and run `python -m app.scripts.check_live_providers "Maggi"` from `backend`. Live checks are opt-in and may fail when a provider changes its DOM or blocks automated browsers.

## Hot Query Cache
The in-memory `HotQueryCache` stores at most 20 successful, fully DTU-verified comparison responses. Keys use normalized query plus location, entries expire after `CACHE_TTL_SECONDS` (180 seconds by default), and eviction favors entries with fewer hits and older access times. Each response exposes `cache.hit`, `cache.age_seconds`, and `cache.fetched_at`; the frontend renders this as a freshness label rather than claiming prices are live at the current second. All-provider failures and unverified provider listings are never cached. A response containing verified listings from one provider and an unavailable second provider may be cached briefly, preserving useful partial results without treating the failed provider as valid. At larger scale, this abstraction can be backed by Redis without changing the search service contract.

## Tech Stack
- Frontend: React, Vite, TypeScript, CSS, Lucide icons
- Backend: Python 3.11+, FastAPI, Pydantic, Playwright, RapidFuzz
- Testing: pytest, pytest-asyncio

## Folder Structure
```text
backend/
  app/
    core/config.py
    models/
    providers/          # location flow and provider-specific selectors
    services/           # normalization, matching, orchestration
    main.py
  tests/
frontend/
  src/
    api/
    types/
    App.tsx
    styles.css
DESIGN_NOTE.md
RECORDING_CHECKLIST.md
```

## Setup

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Development uses clearly labeled demo data by default. Set USE_MOCK_PROVIDERS=false
# only when you want to opt into live provider checks.
uvicorn app.main:app --reload --env-file .env
```

Live browser mode may require Playwright browser installation:
```bash
playwright install chromium
```

Recommended live-development settings in `backend/.env`:
```env
USE_MOCK_PROVIDERS=false
PROVIDER_HEADLESS=false
PROVIDER_USE_PERSISTENT_CONTEXT=true
PROVIDER_BROWSER_CHANNEL=chrome
PROVIDER_MANUAL_BOOTSTRAP=false
PROVIDER_DEBUG=true
```
The normal application flow is automatic: a frontend search calls the API, and the backend reuses one persistent local browser profile per provider without requiring terminal input or manual clicks. The public sites currently reject headless sessions, so local live mode uses visible browser contexts. To give end users a frontend-only experience, run this provider service on a remote backend or replace the adapters with authorized provider APIs. Profiles are local-only and ignored by Git. Manual bootstrap remains an optional developer recovery command only if a provider loses its saved DTU state; it is disabled in normal operation. `PROVIDER_DEBUG=true` writes local failure screenshots under `debug/`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown by the command, normally `http://localhost:5173`.

## Search API
```text
GET /api/health
GET /api/search?q=maggi&location=DTU
```

The API response exposes provider-independent comparison objects and provider status. `location` is intentionally limited to `DTU`; generic Delhi or an unverified provider default location is not accepted as assignment data.

## Matching Logic
Known brands are extracted from structured provider data where available, then from a conservative dictionary. Quantities normalize weight to grams, volume to millilitres, and counts to pieces. Obvious conflicts are rejected before fuzzy scoring: known-brand mismatch, materially different quantity, conflicting variants such as salted/unsalted or zero/regular, and likely multipack-vs-single-pack differences.

Remaining candidates use a deterministic score: 45% title token similarity, 25% brand, 20% quantity, and 10% important variant consistency. Scores at or above 0.85 are high confidence; scores from 0.72 to 0.85 are medium confidence; lower scores remain unpaired.

## Large Result Handling
Provider results are first deduplicated by normalized brand, product family, variant, quantity, unit, and pack count. Listings are then ranked by query-token coverage, brand/family relevance, and a small provider-position signal. Candidate blocking rejects incompatible families, units, quantities, and known variants before entity resolution. Possible pairs are scored globally and assigned greedily one-to-one, so one SKU cannot be reused. The API returns at most `TOP_K_RESULTS` results (15 by default) and exposes hidden pipeline counts for debugging.

When only one provider succeeds, its verified listings remain visible while the unavailable provider is labeled unavailable. The frontend does not claim that one store is cheaper unless both provider prices and verified delivery contexts are present.

## Limitations
- Provider websites and selectors can change, which may make a live adapter unavailable until updated.
- Product titles, bundles, offers, and pack sizes are inherently ambiguous.
- `4 x 70 g` is not automatically treated as the same SKU as a single `280 g` pack.
- Prices and availability can change between the verified location flow and display.
- Provider location behavior may depend on cookies, account state, address eligibility, or UI changes.
- The adapters do not guarantee that every catalogue product is returned.
- Live mode fails closed when DTU delivery cannot be verified; it never substitutes generic Delhi data.

## Responsible Usage
Requests are only triggered by an explicit search, provider calls run concurrently, and identical query plus DTU searches are cached briefly in process. The app does not crawl catalogues or run background scraping loops. Browser sessions are reused during the process so the location step is not repeated unnecessarily for every provider search.

## Testing
```bash
cd backend
pytest
```

The tests cover normalization, units and multipacks, variant and size rejection, and graceful partial failure when one provider cannot verify DTU.

### Opt-in live provider check
Live sites are intentionally excluded from CI. After installing Chromium with `playwright install chromium`, run:
```bash
cd backend
python -m app.scripts.check_live_providers "Maggi"
```
This opens each normal desktop provider flow, reports the resolved DTU location, and prints visible listings. Website DOM changes, security challenges, or unavailable delivery areas are reported as provider failures rather than converted into generic-location prices. In this environment, the manual attempt may be blocked by the providers' anti-automation controls; the app fails closed and does not bypass those controls.

Useful options are `--headed`, `--provider blinkit|zepto`, and `--manual-bootstrap`. A successful partial live response is valid: one provider may return verified listings while the other is reported unavailable.

To bootstrap Zepto's local persistent profile through the normal headed browser flow, run:
```bash
cd backend
python3 -m app.scripts.bootstrap_provider zepto
```
Select Delhi Technological University / Shahbad Daulatpur in the browser and press Enter in the terminal. The adapter verifies the visible location before accepting any listing. If Zepto displays an automated-access block or CAPTCHA, stop; the provider is reported as blocked and no evasion is attempted.
