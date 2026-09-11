from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from .product import ProductListing


class PriceObservation(BaseModel):
    at: str
    price: float


class PublicListing(BaseModel):
    title: str
    price: float
    mrp: float | None = None
    currency: str
    quantity_text: str | None = None
    available: bool
    product_url: str | None = None
    image_url: str | None = None
    source: Literal["blinkit", "zepto"]
    unit_price: float | None = None
    unit_price_basis: str | None = None
    observation_id: str | None = None
    price_history: list[PriceObservation] = Field(default_factory=list)


class Quantity(BaseModel):
    value: float | None = None
    unit: str | None = None


class ComparisonResult(BaseModel):
    match_id: str
    canonical_name: str
    brand: str | None = None
    quantity: Quantity
    match_score: float | None = None
    match_confidence: Literal["high", "medium", "unmatched"]
    blinkit: PublicListing | None = None
    zepto: PublicListing | None = None
    cheaper_provider: Literal["blinkit", "zepto", "same_price", None] = None
    price_difference: float | None = None
    savings_percentage: float | None = None
    query_relevance_score: float | None = None
    match_reasons: list[str] = Field(default_factory=list)
    match_details: "MatchDetails | None" = None


class MatchDetails(BaseModel):
    brand_score: float
    quantity_score: float
    pack_score: float
    variant_score: float
    title_similarity: float
    conflicts: list[str] = Field(default_factory=list)


class PipelineMetadata(BaseModel):
    raw_counts: dict[str, int]
    deduplicated_counts: dict[str, int]
    candidate_pairs: int
    matched_pairs: int
    returned_results: int


class SearchResponse(BaseModel):
    query: str
    location: str
    demo_mode: bool = False
    results: list[ComparisonResult]
    provider_status: dict[str, Literal["ok", "unavailable", "empty"]]
    provider_messages: dict[str, str] = {}
    cache: "CacheMetadata"
    pipeline: PipelineMetadata = Field(default_factory=lambda: PipelineMetadata(raw_counts={}, deduplicated_counts={}, candidate_pairs=0, matched_pairs=0, returned_results=0))


class CacheMetadata(BaseModel):
    hit: bool
    age_seconds: int
    fetched_at: datetime


class HotQuery(BaseModel):
    query: str
    hit_count: int


class HotQueriesResponse(BaseModel):
    queries: list[HotQuery]
