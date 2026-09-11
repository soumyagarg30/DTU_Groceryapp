from fastapi.testclient import TestClient

from app.main import app, search_service
from app.models.search import CacheMetadata, SearchResponse
from datetime import datetime, timezone


def test_hot_query_endpoint_returns_only_query_counters():
    search_service.cache.entries.clear()
    value = SearchResponse(query="maggi", location="DTU", results=[], provider_status={"blinkit": "empty", "zepto": "empty"}, cache=CacheMetadata(hit=False, age_seconds=0, fetched_at=datetime.now(timezone.utc)))
    search_service.cache.put("Maggi", "DTU", value)
    search_service.cache.get("maggi", "DTU")

    response = TestClient(app).get("/api/search/hot")
    assert response.status_code == 200
    assert response.json() == {"queries": [{"query": "maggi", "hit_count": 2}]}
    search_service.cache.entries.clear()
