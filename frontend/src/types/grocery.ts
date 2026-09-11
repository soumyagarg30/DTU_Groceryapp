export type ProviderName = 'blinkit' | 'zepto'
export type ProviderStatus = 'ok' | 'unavailable' | 'empty'

export interface Listing {
  title: string
  price: number
  mrp?: number | null
  currency: string
  quantity_text?: string | null
  available: boolean
  product_url?: string
  image_url?: string | null
  source: ProviderName
  unit_price?: number | null
  observation_id?: string
  price_history?: { at: string; price: number }[]
  unit_price_basis?: string | null
}

export interface ComparisonResult {
  match_id: string
  canonical_name: string
  brand?: string
  quantity: { value?: number | null; unit?: string }
  match_score?: number | null
  match_confidence: 'high' | 'medium' | 'unmatched'
  blinkit?: Listing
  zepto?: Listing
  cheaper_provider?: ProviderName | 'same_price'
  price_difference?: number | null
  savings_percentage?: number | null
  query_relevance_score?: number | null
  match_reasons: string[]
  match_details?: {
    brand_score: number
    quantity_score: number
    pack_score: number
    variant_score: number
    title_similarity: number
    conflicts: string[]
  }
}

export interface HotQuery { query: string; hit_count: number }

export interface SearchResponse {
  query: string
  location: string
  demo_mode: boolean
  results: ComparisonResult[]
  provider_status: Record<ProviderName, ProviderStatus>
  provider_messages?: Record<string, string>
  cache: { hit: boolean; age_seconds: number; fetched_at: string }
  pipeline: { raw_counts: Record<string, number>; deduplicated_counts: Record<string, number>; candidate_pairs: number; matched_pairs: number; returned_results: number }
}
