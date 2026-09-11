````markdown
# DTU Grocery Price Compare

> A location-aware grocery comparison system for DTU hostel students.

DTU Grocery Price Compare helps students compare grocery prices across **Blinkit and Instamart** for delivery specifically to **Delhi Technological University (DTU), Shahbad Daulatpur, Delhi**.

The goal is not just to display two prices, but to make sure those prices belong to the **same product, same delivery location, and sufficiently fresh data**.

---

## Features

### 📍 DTU-Specific Location Verification

Provider prices are accepted only after the delivery context is verified for **DTU / Shahbad Daulatpur**.

If the location cannot be verified:

- The provider is marked unavailable.
- Generic Delhi prices are not used.
- Stale location data is not treated as valid.
- No misleading cross-store comparison is made.

---

### 🔍 Confidence-Aware Product Matching

Products from different providers often have different titles even when they represent the same SKU.

Each listing is normalized using:

- Brand
- Product type
- Variant
- Quantity
- Unit
- Pack structure

Obvious conflicts are rejected before fuzzy similarity is considered.

Examples:

```text
Amul Salted Butter 500g
≠
Amul Unsalted Butter 500g
````

```text
Maggi 70g
≠
Maggi 1kg
```

```text
Maggi 280g Single Pack
≠
Maggi 4 × 70g Multipack
```

The matching score uses:

| Signal           | Weight |
| ---------------- | -----: |
| Title similarity |    45% |
| Brand            |    25% |
| Quantity         |    20% |
| Variant          |    10% |

Confidence levels:

```text
>= 0.85       High Confidence
0.72 - 0.85   Medium Confidence
< 0.72        Unpaired
```

The frontend also exposes a **"Why this match?"** explanation for matched products.

---

### 📊 Large Search Result Handling

Broad searches such as `Maggi` can return many duplicate or loosely related products.

Instead of returning every raw listing, the backend uses the following pipeline:

```text
Raw Provider Results
        ↓
Provider-local Deduplication
        ↓
Query Relevance Ranking
        ↓
Candidate Blocking
        ↓
Entity Resolution
        ↓
One-to-One Matching
        ↓
Top-K Results
```

This prevents:

* Duplicate listings
* Irrelevant products
* Incorrect SKU pairing
* One product being matched multiple times

The default maximum number of returned results is:

```env
TOP_K_RESULTS=15
```

---

### 🎯 Search Filters

The frontend provides three result filters:

* **Matched Only**
* **High Confidence**
* **In Stock Only**

These filters operate on the already processed results and do not trigger additional provider requests.

---

### ⚡ LFU Hot-Query Cache

Repeated hostel searches should not require Blinkit and Instamart to be queried every time.

The backend therefore implements a bounded **LFU (Least Frequently Used) cache**.

```text
Maximum Entries: 20
TTL: 180 seconds
Cache Key: normalized query + location
```

Cache behavior:

* Every cache hit increases `hit_count`.
* Least frequently used entries are removed first.
* If two entries have the same frequency, the least recently accessed entry is evicted.
* Expired entries trigger a fresh provider search.
* Unverified results are not cached as valid comparisons.
* Verified partial-provider results may be cached briefly.

Example metadata:

```json
{
  "cache": {
    "hit": true,
    "age_seconds": 42
  }
}
```

This reduces provider load and improves latency for common hostel searches.

---

### 🛒 Smart Hostel Basket

The Smart Basket extends the system beyond single-product comparison.

Students can add hostel essentials such as:

```text
Maggi
Milk
Bread
Eggs
Butter
```

The basket planner can compare the estimated total cost across available providers while considering:

* Product price
* Pack quantity
* Delivery fee
* Handling fee
* Free-delivery threshold
* Product availability

The basket also supports:

* Cheapest complete basket comparison
* Estimated savings
* Budget tracking
* Equal roommate splitting
* Exact paise distribution

This changes the problem from:

> "Where is this one item cheaper?"

to:

> "Where should I place my complete hostel grocery order?"

---

## Architecture

```text
                     React + Vite Frontend
                              │
                              ▼
                    FastAPI Search Orchestrator
                              │
                              ▼
                       LFU Hot Cache
                         /          \
                      HIT            MISS
                       │              │
                       │              ▼
                       │      Provider Adapters
                       │       /            \
                       │   Blinkit        Instamart
                       │       \            /
                       │        DTU Verification
                       │              │
                       │              ▼
                       │       Product Extraction
                       │              │
                       │              ▼
                       │        Normalization
                       │              │
                       │              ▼
                       │        Deduplication
                       │              │
                       │              ▼
                       │      Relevance Ranking
                       │              │
                       │              ▼
                       │     Candidate Generation
                       │              │
                       │              ▼
                       │       Entity Resolution
                       │              │
                       │              ▼
                       │      Confidence Scoring
                       │              │
                       │              ▼
                       └──────────► Top-K Results
                                      │
                                      ▼
                           Comparison + Basket UI
```

Provider-specific browser and extraction logic stays isolated inside adapters.

The rest of the system works on a common provider-independent `ProductListing` model.

---

## Tech Stack

### Frontend

* React
* Vite
* TypeScript
* CSS
* Lucide Icons

### Backend

* Python 3.11+
* FastAPI
* Pydantic
* Playwright
* RapidFuzz

### Testing

* pytest
* pytest-asyncio

---

## Project Structure

```text
DTU_Groceryapp/
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── models/
│   │   ├── providers/
│   │   ├── services/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── styles.css
│   └── package.json
│
├── DESIGN_NOTE.md
├── RECORDING_CHECKLIST.md
└── README.md
```

---

## Setup

### Backend

```bash
cd backend
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Start the backend:

```bash
python3 -m uvicorn app.main:app --reload --env-file .env
```

Backend URL:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

---

### Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend normally runs at:

```text
http://localhost:5173
```

---

## Environment Configuration

Example `backend/.env`:

```env
USE_MOCK_PROVIDERS=false

PROVIDER_HEADLESS=false
PROVIDER_USE_PERSISTENT_CONTEXT=true
PROVIDER_BROWSER_CHANNEL=chrome
PROVIDER_MANUAL_BOOTSTRAP=false
PROVIDER_DEBUG=true

CACHE_TTL_SECONDS=180
HOT_QUERY_CACHE_MAX_ENTRIES=20
TOP_K_RESULTS=15
```

---

## Demo Mode

For deterministic local testing:

```env
USE_MOCK_PROVIDERS=true
```

Restart the backend after changing the environment file.

Demo responses are explicitly labelled:

```text
Demo data
```

Mock data is never silently presented as live provider data.

---

## Live Mode

Install Playwright Chromium if required:

```bash
playwright install chromium
```

Set:

```env
USE_MOCK_PROVIDERS=false
```

Then start the backend:

```bash
python3 -m uvicorn app.main:app --reload --env-file .env
```

Live provider adapters use persistent browser contexts so DTU location state can be reused between searches.

If a provider blocks automation or DTU cannot be verified, the provider is marked unavailable instead of returning unverified prices.

---

## API

### Health Check

```http
GET /api/health
```

### Search

```http
GET /api/search?q=maggi&location=DTU
```

Example:

```bash
curl "http://127.0.0.1:8000/api/search?q=maggi&location=DTU"
```

The response can include:

* Provider status
* DTU location verification
* Product comparison results
* Match confidence
* Match reasons
* Cache metadata
* Freshness metadata
* Search pipeline statistics

---

### Basket Optimization

```http
POST /api/basket/optimize
```

The basket optimizer accepts:

* Product name
* Pack quantity
* Provider prices
* Delivery fees
* Handling fees
* Optional free-delivery thresholds

It calculates an estimated cheapest basket allocation.

It does **not** place orders.

---

## Live Provider Check

Live providers are intentionally excluded from deterministic automated tests.

Run:

```bash
cd backend
python3 -m app.scripts.check_live_providers "Maggi"
```

Example headed check:

```bash
python3 -m app.scripts.check_live_providers \
  "Maggi" \
  --headed \
  --provider blinkit
```

The checker reports:

* Resolved delivery location
* DTU verification status
* Number of extracted products
* Sample listings
* Failure reason when applicable

---

## Testing

Run backend tests:

```bash
cd backend
pytest
```

Build the frontend:

```bash
cd frontend
npm run build
```

The test suite covers areas including:

* Product normalization
* Quantity extraction
* Multipack parsing
* Variant conflicts
* Product matching
* Provider failure isolation
* LFU cache behavior
* Cache eviction
* Deduplication
* Query relevance
* Candidate blocking
* One-to-one matching
* Top-K results
* Basket optimization

---

## Reliability Principles

The system follows a conservative comparison policy.

```text
Wrong Location
→ Reject Provider Data

Obvious SKU Conflict
→ Reject Match

Provider Failure
→ Return Valid Partial Results

Both Providers Fail
→ Do Not Fabricate Comparison

Cached Result
→ Show Cache Age

Uncertain Product Match
→ Leave Unpaired
```

> **Correctness over coverage. Verified data over false confidence.**

---

## Limitations

* Provider website DOM structures can change.
* Providers may block automated browsers.
* Product bundles and promotional packs can be ambiguous.
* `4 × 70g` is not automatically considered the same SKU as a single `280g` pack.
* Prices and stock may change after a result is fetched.
* Not every catalogue item is guaranteed to be returned.
* Live mode fails closed when DTU delivery cannot be verified.
* Basket delivery and handling fees are estimates.
* Coupons, surge pricing, and checkout-specific offers are not currently modeled.

---

## Responsible Usage

The application only performs provider searches when a user explicitly requests them.

It does not:

* Crawl entire catalogues
* Run continuous scraping loops
* Bypass CAPTCHA
* Bypass provider security controls
* Treat unverified locations as valid
* Silently substitute demo data for live data

Short-lived caching and persistent provider sessions reduce unnecessary requests.

---

## Design Philosophy

DTU Grocery Price Compare is designed around three questions:

1. **Is this price actually for DTU?**
2. **Are these two listings actually the same product?**
3. **Is the information fresh enough to trust?**

The normalization, entity-resolution pipeline, LFU cache, result ranking, filters, and Smart Basket are all built around answering these questions reliably.

---

## Future Improvements

* Redis-backed distributed cache
* Support for multiple delivery locations
* Authorized provider APIs
* Historical price tracking
* Improved entity-resolution models
* Provider health monitoring
* Larger basket optimization
* Personalized hostel essentials

---

## Assignment

Built for the **CarDekho Group DTU Campus Assignment**.

The project prioritizes **reliable comparisons, explainable matching, responsible provider handling, and practical hostel usability**.

````

**Copy everything inside the outer ```markdown ... ``` block and paste it directly into GitHub's `README.md` editor.**
````
