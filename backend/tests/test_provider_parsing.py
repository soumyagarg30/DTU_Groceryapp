from app.providers.parsing import parse_first_number, parse_inr_price, parse_visible_prices


def test_parse_inr_price_variants():
    assert parse_inr_price("₹58") == 58.0
    assert parse_inr_price("₹ 58.00") == 58.0
    assert parse_inr_price("MRP INR 1,249.50") == 1249.5
    assert parse_inr_price("no price") is None


def test_parse_first_number_for_visible_quantity_text():
    assert parse_first_number("4 x 70 g") == 4.0
    assert parse_first_number("500 ml") == 500.0


def test_parse_visible_prices_supports_currencyless_provider_text():
    assert parse_visible_prices("30% OFF\n208\n300") == [208.0, 300.0]
