from fastapi.testclient import TestClient
from app.main import app
from app.services.basket import BasketRequest, optimize_basket


def calculate(items, **fees):
    return optimize_basket(BasketRequest(items=items, **fees))


ITEMS = [dict(name='Milk', blinkit=40, zepto=50), dict(name='Bread', blinkit=50, zepto=40)]


def test_delivery_can_make_one_store_cheaper_than_split():
    result = calculate(ITEMS)
    assert result['best']['total'] == 115
    assert len(result['best']['stores']) == 1
    assert result['savings_vs_single'] == 0


def test_split_saves_when_delivery_is_low():
    result = calculate(ITEMS, blinkit={'delivery': 2}, zepto={'delivery': 2})
    assert result['best']['total'] == 84
    assert result['savings_vs_single'] == 8
    assert result['best']['assignment'] == ['blinkit', 'zepto']


def test_threshold_can_reverse_cheapest_item_assignment():
    result = calculate(ITEMS, blinkit={'delivery': 25, 'free_above': 90, 'handling': 3}, zepto={'delivery': 25})
    assert result['best']['total'] == 93
    assert result['best']['assignment'] == ['blinkit', 'blinkit']


def test_missing_store_is_not_a_zero_price_and_quantity_is_applied():
    result = calculate([dict(name='Milk', blinkit=10.01, quantity=3)], blinkit={'delivery': 0})
    assert result['best']['total'] == 30.03
    assert result['single_store']['zepto'] is None


def test_no_complete_single_store_has_no_savings_claim():
    result = calculate([dict(name='Milk', blinkit=20), dict(name='Bread', zepto=30)])
    assert result['savings_vs_single'] is None
    assert result['best']['total'] == 100


def test_api_rejects_unavailable_and_oversized_baskets():
    client = TestClient(app)
    for items in [[], [dict(name='Milk')], [ITEMS[0]] * 13, [dict(name='Milk', blinkit=-1)], [dict(name='Milk', blinkit=1, quantity=0)]]:
        assert client.post('/api/basket/optimize', json={'items': items}).status_code == 422


def test_endpoint_and_cors_support_frontend():
    client = TestClient(app)
    response = client.post('/api/basket/optimize', json={'items': ITEMS})
    assert response.status_code == 200
    assert response.json()['estimated'] is True
    response = client.options('/api/basket/optimize', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
    assert response.status_code == 200
