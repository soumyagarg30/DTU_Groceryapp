import pytest

from app.models.product import ProductListing
from app.services.pricing import calculate_savings_percentage, calculate_unit_price


def listing(price: float, quantity: str | None) -> ProductListing:
    return ProductListing(provider="blinkit", title="Test product", price=price, quantity_text=quantity, available=True)


@pytest.mark.parametrize(("price", "quantity", "expected", "basis"), [
    (60, "280 g", 21.43, "100 g"),
    (200, "1 kg", 20.0, "100 g"),
    (80, "500 ml", 16.0, "100 ml"),
    (80, "1 L", 8.0, "100 ml"),
    (120, "12 pieces", 10.0, "piece"),
])
def test_calculate_unit_price(price, quantity, expected, basis):
    result = calculate_unit_price(listing(price, quantity))
    assert result is not None
    assert result.unit_price == expected
    assert result.unit_price_basis == basis


def test_no_unit_price_without_quantity():
    assert calculate_unit_price(listing(60, None)) is None


def test_savings_percentage_uses_higher_price():
    assert calculate_savings_percentage(60, 62) == 3.2
