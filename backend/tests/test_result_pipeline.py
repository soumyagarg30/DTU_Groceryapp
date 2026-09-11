import pytest

from app.models.product import ProductListing
from app.providers.base import GroceryProvider
from app.services.matcher import match_products
from app.services.result_pipeline import deduplicate_listings, rank_by_query_relevance
from app.services.search_service import SearchService


def listing(title: str, quantity: str, price: float = 50) -> ProductListing:
    return ProductListing(provider="blinkit", title=title, brand="Maggi", price=price, quantity_text=quantity, available=True)


def test_provider_dedupe_keeps_pack_sizes_and_variants_separate():
    values = deduplicate_listings([
        listing("Maggi Masala Instant Noodles", "280 g", 60),
        listing("MAGGI Masala Instant Noodles", "280g", 62),
        listing("Maggi Masala Instant Noodles", "70 g", 20),
        listing("Maggi Atta Noodles", "290 g", 90),
    ])
    assert len(values) == 3
    assert {item.quantity_text for item in values} == {"280 g", "70 g", "290 g"}


def test_relevance_ranks_query_brand_and_family_results():
    ranked = rank_by_query_relevance([
        listing("Maggi Tomato Ketchup", "500 g"),
        listing("Maggi Masala Instant Noodles", "280 g"),
        listing("Maggi Masala-ae-Magic", "72 g"),
    ], "Maggi noodles")
    assert ranked[0].title == "Maggi Masala Instant Noodles"
    assert ranked[0].metadata["query_relevance_score"] >= ranked[-1].metadata["query_relevance_score"]


def test_candidate_generation_rejects_unrelated_family_and_preserves_one_to_one():
    left = [listing("Maggi Masala Noodles", "280 g"), listing("Maggi Masala Noodles", "280 g", 61)]
    right = [listing("Maggi Tomato Ketchup", "500 g")]
    matches, unmatched_left, unmatched_right, candidates = match_products(left, right)
    assert matches == []
    assert len(unmatched_left) == 2
    assert len(unmatched_right) == 1
    assert candidates == 0


class FixtureProvider(GroceryProvider):
    def __init__(self, name: str, count: int):
        self.name = name
        self.count = count
        self.calls = 0

    async def establish_location(self, location):
        assert location == "DTU"

    async def search(self, query, location):
        self.calls += 1
        return [ProductListing(provider=self.name, title=f"Maggi Masala Noodles {index + 1} g", brand="Maggi", price=20 + index, quantity_text=f"{index + 1} g", available=True) for index in range(self.count)]


@pytest.mark.asyncio
async def test_search_caps_results_and_exposes_pipeline_counts():
    blinkit = FixtureProvider("blinkit", 25)
    zepto = FixtureProvider("zepto", 25)
    service = SearchService({"blinkit": blinkit, "zepto": zepto}, cache_ttl_seconds=180)
    response = await service.search("maggi")
    assert len(response.results) <= 15
    assert response.pipeline.raw_counts == {"blinkit": 25, "zepto": 25}
    assert response.pipeline.returned_results == len(response.results)
    assert response.pipeline.candidate_pairs > 0
