import BasketPlanner, { type BasketEntry } from './components/BasketPlanner'
import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Check, MapPin, Search, Store, TriangleAlert } from 'lucide-react'
import { getHotQueries, searchGroceries } from './api/groceryApi'
import type { ComparisonResult, HotQuery, Listing, ProviderName, SearchResponse } from './types/grocery'

const STARTER_QUERIES = ['Maggi', 'Milk', 'Bread', 'Eggs', 'Butter']

function money(value?: number | null) { return value == null || !Number.isFinite(value) ? '—' : `₹${value.toFixed(value % 1 ? 2 : 0)}` }
function providerLabel(provider: ProviderName) { return provider === 'blinkit' ? 'Blinkit' : 'Zepto' }
function ageLabel(age: number, cached: boolean) {
  if (age < 60) return cached ? `Cached result • ${age}s old` : `Checked ${age}s ago`
  const minutes = Math.floor(age / 60)
  return cached ? `Cached result • ${minutes}m old` : `Checked ${minutes}m ago`
}
function providerMessage(message: string) {
  return message === 'blocked' ? 'Automated access was blocked by the provider. No security bypass was attempted.' : message
}

function ProviderListing({ listing, provider, unavailable }: { listing?: Listing; provider: ProviderName; unavailable: boolean }) {
  if (!listing) return <div className="listing missing"><div className="listing-heading"><Store size={15} />{providerLabel(provider)}</div><p>{unavailable ? 'Currently unavailable' : 'No confident match'}</p></div>
  return <div className="listing">
    <div className="listing-heading"><Store size={15} />{providerLabel(provider)}<span className={listing.available ? 'availability' : 'availability muted'}>{listing.available ? 'In stock' : 'Unavailable'}</span></div>
    <div className="price-row"><strong>{money(listing.price)}</strong>{listing.mrp && listing.mrp > listing.price && <del>{money(listing.mrp)}</del>}</div>
    {listing.unit_price != null && <p className="unit-price">{money(listing.unit_price)} / {listing.unit_price_basis}</p>}
    <p>{listing.quantity_text ?? 'Quantity unavailable'}</p><p className="verified">✓ DTU verified</p>
  </div>
}

export function ComparisonCard({ result, providerStatus, onAdd, added, full }: { onAdd: () => void; added: boolean; full: boolean; result: ComparisonResult; providerStatus: SearchResponse['provider_status'] }) {
  const missingProvider: ProviderName = result.blinkit ? 'zepto' : 'blinkit'
  const hasBoth = Boolean(result.blinkit && result.zepto)
  const savings = result.cheaper_provider && result.cheaper_provider !== 'same_price'
    ? `${money(result.price_difference)} cheaper on ${providerLabel(result.cheaper_provider)}${result.savings_percentage != null ? ` • ${result.savings_percentage}% less` : ''}`
    : result.cheaper_provider === 'same_price' ? 'Same price' : null
  const message = result.match_confidence === 'unmatched'
    ? providerStatus[missingProvider] === 'unavailable' ? 'Cross-store price comparison unavailable' : `Not confidently matched on ${providerLabel(missingProvider)}`
    : savings ?? 'Likely match — price winner withheld until confidence is high'
  const confidence = Math.round((result.match_score ?? 0) * 100)
  const ambiguity = result.match_confidence === 'medium' ? `Likely same product — ${confidence}%. Some listing details differ, so price comparison is withheld.` : null

  return <article className="comparison-card">
    <div className="product-header"><div><span className="eyebrow">{result.brand ?? 'Grocery item'}</span><h2>{result.canonical_name}</h2><p>{result.quantity.value ? `${result.quantity.value} ${result.quantity.unit}` : 'Quantity not confirmed'}</p></div><span className={`confidence ${result.match_confidence}`}>{result.match_confidence === 'unmatched' ? 'Unmatched' : `${confidence}% ${result.match_confidence}`}</span></div>
    <div className="listings"><ProviderListing listing={result.blinkit} provider="blinkit" unavailable={providerStatus.blinkit === 'unavailable'} /><ProviderListing listing={result.zepto} provider="zepto" unavailable={providerStatus.zepto === 'unavailable'} /></div>
    <button className="basket-button add-basket" disabled={added || full || result.match_confidence !== 'high' || ![result.blinkit, result.zepto].some(l => l?.available)} onClick={onAdd}>{added ? 'Added to basket' : full ? 'Basket full (12 items)' : result.match_confidence !== 'high' ? 'Basket requires a high-confidence match' : 'Add to hostel basket'}</button>
    <div className="comparison-note"><Check size={15} />{message}</div>
    {ambiguity && <p className="ambiguity">⚠ {ambiguity}</p>}
    {hasBoth && <details className="match-reason"><summary>Why this match?</summary><div><strong>Match confidence: {confidence}%</strong><p>{result.match_confidence === 'high' ? 'High confidence' : 'Medium confidence'}</p>{result.match_reasons.map((reason) => <p key={reason}>✓ {reason}</p>)}</div></details>}
  </article>
}

function App() {
  const [basket, setBasket] = useState<BasketEntry[]>([])
  const [query, setQuery] = useState('')
  const [data, setData] = useState<SearchResponse | null>(null)
  const [hotQueries, setHotQueries] = useState<HotQuery[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [matchedOnly, setMatchedOnly] = useState(false)
  const [highOnly, setHighOnly] = useState(false)
  const [inStockOnly, setInStockOnly] = useState(false)

  useEffect(() => { getHotQueries().then(setHotQueries).catch(() => setHotQueries([])) }, [])

  async function runSearch(value: string) {
    const cleaned = value.trim()
    if (cleaned.length < 2 || loading) return
    setQuery(cleaned); setLoading(true); setError('')
    try { setData(await searchGroceries(cleaned)); void getHotQueries().then(setHotQueries).catch(() => {}) }
    catch (caught) { setData(null); setError(caught instanceof Error ? caught.message : 'The grocery service is unavailable.') }
    finally { setLoading(false) }
  }
  function submit(event: React.FormEvent) { event.preventDefault(); void runSearch(query) }

  const shownResults = useMemo(() => (data?.results ?? []).filter((result) => {
    if (matchedOnly && !(result.blinkit && result.zepto)) return false
    if (highOnly && result.match_confidence !== 'high') return false
    if (inStockOnly && ![result.blinkit, result.zepto].filter(Boolean).every((listing) => listing?.available)) return false
    return true
  }), [data, matchedOnly, highOnly, inStockOnly])
  const providersUnavailable = data && Object.values(data.provider_status).every((status) => status === 'unavailable')
  const chips = hotQueries.length ? hotQueries.map((item) => item.query) : STARTER_QUERIES

  return <main>
    <header className="topbar"><div className="brand"><div className="brand-mark"><Store size={17} /></div><div><strong>Grocery Compare</strong><span>DTU</span></div></div><div className="location"><MapPin size={14} /><div><small>Delivering to</small><strong>Delhi Technological University</strong></div></div></header>
    <section className="hero"><div className="hero-copy"><span className="section-label">Blinkit vs Zepto</span><h1>Compare grocery prices around DTU.</h1><p>Search once to see verified prices, pack sizes, and unit costs from stores that deliver to campus.</p></div><form className="search-panel" onSubmit={submit}><label htmlFor="query">What are you looking for?</label><div className="search-line"><Search size={20} /><input id="query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search milk, Maggi, butter…" /><button type="submit" disabled={query.trim().length < 2 || loading}>{loading ? 'Checking stores…' : 'Compare prices'}<ArrowRight size={17} /></button></div><div className="search-meta"><div className="hot-searches"><span>{hotQueries.length ? 'Popular' : 'Suggestions'}</span>{chips.slice(0, 8).map((chip) => <button type="button" key={chip} onClick={() => void runSearch(chip)}>{chip}</button>)}</div><div className="scope"><MapPin size={13} /><span>DTU, Shahbad Daulatpur</span></div></div></form></section>
    <BasketPlanner entries={basket} setEntries={setBasket} />
    {data?.demo_mode && <div className="demo-banner">Demo data is enabled. Prices are examples, not live listings.</div>}{error && <div className="message error"><TriangleAlert size={17} />{error}</div>}
    {data && <section className="results"><div className="results-head"><div><span className="section-label">{data.results.length} results</span><h2>{providersUnavailable ? 'Stores are unavailable' : data.results.length ? `Results for “${data.query}”` : `No results for “${data.query}”`}</h2><div className="freshness">{ageLabel(data.cache.age_seconds, data.cache.hit)}{data.cache.hit && ' · served from cache'}</div></div><div className="provider-status">{(['blinkit', 'zepto'] as ProviderName[]).map((provider) => <div key={provider} className={`provider-pill ${data.provider_status[provider]}`}><i /><span><strong>{providerLabel(provider)}</strong><small>{data.provider_status[provider] === 'ok' ? 'DTU verified' : data.provider_status[provider]}</small></span></div>)}</div></div>
      {Object.entries(data.provider_messages ?? {}).map(([provider, message]) => <div className="message" key={provider}><strong>{provider === 'blinkit' ? 'Blinkit' : 'Zepto'}:</strong> {providerMessage(message)}</div>)}
      <div className="filters"><label><input type="checkbox" checked={matchedOnly} onChange={(event) => setMatchedOnly(event.target.checked)} /> Matched only</label><label><input type="checkbox" checked={highOnly} onChange={(event) => setHighOnly(event.target.checked)} /> High confidence only</label><label><input type="checkbox" checked={inStockOnly} onChange={(event) => setInStockOnly(event.target.checked)} /> In stock only</label></div>
      {shownResults.map((result) => <ComparisonCard key={result.match_id} result={result} providerStatus={data.provider_status} added={basket.some(e => e.result.match_id === result.match_id)} full={basket.length >= 12} onAdd={() => setBasket(previous => previous.length >= 12 || previous.some(e => e.result.match_id === result.match_id) ? previous : [...previous, { result, quantity: 1, demo: data.demo_mode, fetched: data.cache.fetched_at }])} />)}
      <details className="diagnostics"><summary>View search details</summary><div className="diagnostic-grid"><span>Blinkit raw: {data.pipeline.raw_counts.blinkit ?? 0}</span><span>Zepto raw: {data.pipeline.raw_counts.zepto ?? 0}</span><span>Blinkit after dedupe: {data.pipeline.deduplicated_counts.blinkit ?? 0}</span><span>Zepto after dedupe: {data.pipeline.deduplicated_counts.zepto ?? 0}</span><span>Candidate pairs: {data.pipeline.candidate_pairs}</span><span>Matched pairs: {data.pipeline.matched_pairs}</span><span>Returned: {data.pipeline.returned_results}</span><span>Cache: {data.cache.hit ? 'Hit' : 'Miss'} · {data.cache.age_seconds}s old</span></div></details>
    </section>}
    <footer>Prices and availability change. Every comparison is checked against the DTU delivery context.</footer>
  </main>
}

export default App
