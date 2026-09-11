from app.services.normalization import extract_brand, extract_quantity, normalize_text


def test_normalizes_title_and_brand():
    assert normalize_text("MAGGI Masala Noodles 280 GM") == "maggi masala noodles"
    assert extract_brand("MAGGI Masala Noodles 280 GM") == "maggi"


def test_extracts_base_weight():
    quantity = extract_quantity("1 kg")
    assert quantity.total_value == 1000
    assert quantity.unit == "g"


def test_extracts_multipack_without_losing_pack_count():
    quantity = extract_quantity("4 x 70 g")
    assert quantity.total_value == 280
    assert quantity.unit_value == 70
    assert quantity.pack_count == 4
