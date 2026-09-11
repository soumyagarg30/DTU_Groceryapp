import type { HotQuery, SearchResponse } from '../types/grocery'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function searchGroceries(query: string): Promise<SearchResponse> {
  const response = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}&location=DTU`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? 'The grocery service is unavailable.')
  }
  return response.json() as Promise<SearchResponse>
}

export async function getHotQueries(): Promise<HotQuery[]> {
  const response = await fetch(`${API_BASE}/api/search/hot`)
  if (!response.ok) return []
  const body = await response.json() as { queries: HotQuery[] }
  return body.queries
}
