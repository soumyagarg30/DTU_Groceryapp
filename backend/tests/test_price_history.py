from datetime import datetime, timedelta, timezone
from app.models.search import CacheMetadata, ComparisonResult, PublicListing, Quantity, SearchResponse
from app.services.price_history import PriceHistory


def sample(price=40, *, cached=False, demo=False, available=True, offset=0):
    return SearchResponse(query='Milk', location='DTU', demo_mode=demo, provider_status={'blinkit': 'ok'}, cache=CacheMetadata(hit=cached, age_seconds=0, fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=offset)), results=[ComparisonResult(match_id='a', canonical_name='Amul Milk', quantity=Quantity(value=500, unit='ml'), match_confidence='unmatched', blinkit=PublicListing(title='Amul Milk 500 ml', price=price, currency='INR', available=available, source='blinkit', quantity_text='500 ml'))])


def test_history_survives_new_instance_and_deduplicates_cache(tmp_path):
    path = tmp_path / 'prices.sqlite3'
    first = sample()
    PriceHistory(path).enrich(first)
    second = sample(35, offset=1)
    PriceHistory(path).enrich(second)
    assert [p.price for p in second.results[0].blinkit.price_history] == [40, 35]
    cached = sample(35, cached=True, offset=2)
    PriceHistory(path).enrich(cached)
    assert len(cached.results[0].blinkit.price_history) == 2


def test_modes_sizes_and_availability_do_not_pollute_history(tmp_path):
    history = PriceHistory(tmp_path / 'prices.sqlite3')
    history.enrich(sample())
    for value in [sample(demo=True), sample(available=False, offset=1)]:
        history.enrich(value)
        assert len(value.results[0].blinkit.price_history) == 1
    larger = sample()
    larger.results[0].blinkit.quantity_text = '1 l'
    history.enrich(larger)
    assert len(larger.results[0].blinkit.price_history) == 1
    unavailable = sample(20, available=False, offset=2)
    history.enrich(unavailable)
    assert unavailable.results[0].blinkit.price_history[-1].price == 40


def test_only_latest_twenty_observations_retained(tmp_path):
    history = PriceHistory(tmp_path / 'prices.sqlite3')
    for i in range(25):
        value = sample(i, offset=i)
        history.enrich(value)
    assert len(value.results[0].blinkit.price_history) == 20
    assert value.results[0].blinkit.price_history[0].price == 5
