import { useEffect, useState } from 'react'
import type { ComparisonResult, ProviderName } from '../types/grocery'

export interface BasketEntry { result: ComparisonResult; quantity: number; demo: boolean; fetched: string }
interface Fees { delivery: number; handling: number; free_above: number | null }
interface Plan { total: number; stores: Partial<Record<ProviderName, { subtotal: number; fees: number; total: number; item_indices: number[] }>> }
interface Recommendation { best: Plan; single_store: Record<ProviderName, Plan | null>; savings_vs_single: number | null }
const providers: ProviderName[] = ['blinkit', 'zepto']
const rupees = (n: number) => `₹${n.toFixed(2)}`
const label = (s: string) => s === 'blinkit' ? 'Blinkit' : 'Zepto'

export default function BasketPlanner({ entries, setEntries }: { entries: BasketEntry[]; setEntries: React.Dispatch<React.SetStateAction<BasketEntry[]>> }) {
  const [fees, setFees] = useState<Record<ProviderName, Fees>>({ blinkit: { delivery: 25, handling: 0, free_above: null }, zepto: { delivery: 25, handling: 0, free_above: null } })
  const [budget, setBudget] = useState(500)
  const [people, setPeople] = useState(2)
  const [calculation, setCalculation] = useState<{ entries: BasketEntry[]; fees: Record<ProviderName, Fees>; result: Recommendation } | null>(null)
  const answer = calculation?.entries === entries && calculation.fees === fees ? calculation.result : null
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    setCalculation(null); setError('')
    if (!entries.length) { setLoading(false); return }
    const controller = new AbortController()
    setLoading(true)
    const timer = setTimeout(() => {
      void fetch(`${import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'}/api/basket/optimize`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ ...fees, items: entries.map(({ result, quantity }) => ({ name: result.canonical_name, quantity, ...Object.fromEntries(providers.map(p => [p, result[p]?.available ? result[p]!.price : null])) })) }),
      }).then(async response => { if (!response.ok) throw new Error('Could not calculate this basket. Check the fee inputs and try again.'); return response.json() as Promise<Recommendation> })
        .then(value => { if (!controller.signal.aborted) setCalculation({ entries, fees, result: value }) })
        .catch(e => { if (!controller.signal.aborted) setError(e.message) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [entries, fees])
  const totalCents = Math.round((answer?.best.total ?? 0) * 100)
  const share = Math.floor(totalCents / people)
  const remainder = totalCents % people
  return <section className="basket-panel" aria-labelledby="basket-title">
    <div className="basket-heading"><div><span className="section-label">Built for hostel life</span><h2 id="basket-title">The smarter campus basket</h2><p>One store or two? Find the lowest estimated total, including your delivery assumptions.</p></div><span className="basket-count">{entries.length}/12 items</span></div>
    {!entries.length ? <p className="basket-empty">Search above and add high-confidence, in-stock matches to build your basket. Compare a whole grocery run, then split the bill with your roommates.</p> : <>
      <p className="basket-disclaimer">{entries.some(e => e.demo) ? 'Contains demo prices. ' : ''}Saved search snapshots, not checkout quotes. Prices are not refreshed automatically; remove and re-add items after a new search.</p>
      <div className="basket-items">{entries.map((entry, i) => <div className="basket-item" key={entry.result.match_id}><div><strong>{entry.result.canonical_name}</strong><small>{entry.result.quantity.value} {entry.result.quantity.unit} · {entry.demo ? 'Demo' : 'Search snapshot'} · {new Date(entry.fetched).toLocaleString()}</small></div><label>Packs <input aria-label={`Packs of ${entry.result.canonical_name}`} type="number" min="1" max="99" value={entry.quantity} onChange={e => setEntries(previous => previous.map((item, index) => index === i ? { ...item, quantity: Math.max(1, Math.min(99, Math.trunc(Number(e.target.value) || 1))) } : item))} /></label><button className="basket-button" onClick={() => setEntries(previous => previous.filter((_, index) => index !== i))}>Remove</button></div>)}</div>
      <details className="fee-settings"><summary>Edit delivery & handling assumptions</summary><p>Defaults are illustrative. Enter checkout fees; leave the free-delivery threshold blank if unknown. Handling applies to each store used.</p><div className="fee-grid">{providers.map(provider => <fieldset key={provider}><legend>{label(provider)}</legend>{(['delivery', 'handling', 'free_above'] as const).map(field => <label key={field}>{field === 'free_above' ? 'Free delivery at ₹' : `${field === 'delivery' ? 'Delivery' : 'Handling'} ₹`}<input type="number" min={field === 'free_above' ? '0.01' : '0'} max={field === 'free_above' ? '100000' : '10000'} step="0.01" placeholder="Unknown" value={fees[provider][field] ?? ''} onChange={e => setFees(previous => ({ ...previous, [provider]: { ...previous[provider], [field]: field === 'free_above' && !e.target.value ? null : Math.max(field === 'free_above' ? 0.01 : 0, Math.min(field === 'free_above' ? 100000 : 10000, Number(e.target.value))) } }))} /></label>)}</fieldset>)}</div></details>
      <div aria-live="polite">{loading && <p>Finding your best basket…</p>}{error && <p role="alert">{error}</p>}{answer && <><div className="basket-summary"><span>Lowest estimated total<strong>{rupees(answer.best.total)}</strong></span><p>{Object.keys(answer.best.stores).length === 1 ? 'One checkout is best with these fees.' : 'Splitting across two stores is best with these fees.'}<br />{answer.savings_vs_single !== null ? `${rupees(answer.savings_vs_single)} saved versus the cheapest complete single-store basket.` : 'No single store can fulfill every selected item.'}</p></div><div className="fee-grid">{providers.map(p => <div className="store-plan" key={p}><strong>{label(p)}</strong>{answer.best.stores[p] ? <><ul>{answer.best.stores[p]!.item_indices.map(i => <li key={i}>{entries[i].quantity} × {entries[i].result.canonical_name}</li>)}</ul><p>Items {rupees(answer.best.stores[p]!.subtotal)} + fees {rupees(answer.best.stores[p]!.fees)}</p><strong>{rupees(answer.best.stores[p]!.total)}</strong></> : <p>No order needed</p>}<small>All items here: {answer.single_store[p] ? rupees(answer.single_store[p]!.total) : 'Unavailable'}</small></div>)}</div></>}</div>
      <div className="budget-controls"><label>Basket budget ₹<input type="number" min="0" max="1000000" value={budget} onChange={e => setBudget(Math.max(0, Math.min(1000000, Number(e.target.value))))} /></label><label>Roommates (including you)<input type="number" min="1" max="50" value={people} onChange={e => setPeople(Math.max(1, Math.min(50, Math.trunc(Number(e.target.value) || 1))))} /></label></div>
      {answer && <div className="budget-result"><p>{answer.best.total <= budget ? `${rupees(budget - answer.best.total)} left in your budget` : `${rupees(answer.best.total - budget)} over budget`}</p><progress aria-label="Budget used" max={budget || 1} value={Math.min(answer.best.total, budget || 1)} /><p>Equal split: {remainder ? `${remainder} pay ${rupees((share + 1) / 100)}; ${people - remainder} pay ${rupees(share / 100)}` : `${rupees(share / 100)} each for ${people} ${people === 1 ? 'person' : 'people'}`}.</p></div>}
    </>}
  </section>
}
