from app.models.product import ProductListing
from app.services.matcher import match_breakdown, match_products, score_match


def listing(title: str, brand: str, quantity: str) -> ProductListing:
    return ProductListing(provider="blinkit", title=title, brand=brand, price=50, quantity_text=quantity, available=True)


def test_matches_equivalent_maggi_titles():
    assert score_match(listing("Maggi Masala Noodles 280g", "Maggi", "280g"), listing("MAGGI Masala Instant Noodles 280 g", "Maggi", "280 g")) >= 0.72


def test_rejects_conflicting_variants():
    assert score_match(listing("Amul Salted Butter 500g", "Amul", "500g"), listing("Amul Unsalted Butter 500g", "Amul", "500g")) == 0
    assert score_match(listing("Coke Zero 750ml", "Coke", "750ml"), listing("Coke Regular 750ml", "Coke", "750ml")) == 0
    assert score_match(listing("Maggi Spicy Cheesy Cup Noodles 71.5g", "Maggi", "71.5g"), listing("Maggi Spicy Cheesy Noodles 76g", "Maggi", "76g")) == 0


def test_rejects_different_sizes():
    assert score_match(listing("Maggi Noodles 280g", "Maggi", "280g"), listing("Maggi Noodles 70g", "Maggi", "70g")) == 0


def test_match_breakdown_reports_components_and_conflicts():
    good = match_breakdown(listing("Maggi Masala Noodles 280g", "Maggi", "280g"), listing("MAGGI Masala Instant Noodles 280 g", "Maggi", "280 g"))
    assert good.brand_score == good.quantity_score == good.pack_score == good.variant_score == 1
    assert good.title_similarity > 0.7
    assert good.conflicts == ()
    bad = match_breakdown(listing("Maggi Noodles 70g", "Maggi", "70g"), listing("Maggi Noodles 1kg", "Maggi", "1kg"))
    assert "materially different quantities" in bad.conflicts
    assert bad.final_confidence == 0


def test_greedy_matching_is_one_to_one():
    left = [listing("Maggi Masala Noodles 280g", "Maggi", "280g"), listing("Maggi Instant Masala Noodles 280g", "Maggi", "280g")]
    right = [listing("MAGGI Masala Instant Noodles 280 g", "Maggi", "280g")]
    matches, unmatched_left, unmatched_right, candidates = match_products(left, right)
    assert len(matches) == 1
    assert len(unmatched_left) == 1
    assert unmatched_right == []
    assert candidates == 2
