from .base import GroceryProvider
from ..models.product import ProductListing

MOCK_PRODUCTS = {
    "blinkit": {
        "maggi": [ProductListing(provider="blinkit", external_id="b-maggi-280", title="Maggi 2-Minute Masala Noodles 280 g", brand="Maggi", price=58, mrp=60, quantity_text="280 g", normalized_quantity_value=280, normalized_quantity_unit="g", available=True, product_url="https://blinkit.com/", raw_title="Maggi 2-Minute Masala Noodles 280 g")],
        "amul butter": [ProductListing(provider="blinkit", external_id="b-amul-500", title="Amul Pasteurised Butter Salted 500 g", brand="Amul", price=285, mrp=300, quantity_text="500 g", normalized_quantity_value=500, normalized_quantity_unit="g", available=True, product_url="https://blinkit.com/", raw_title="Amul Pasteurised Butter Salted 500 g")],
    },
    "zepto": {
        "maggi": [ProductListing(provider="zepto", external_id="z-maggi-280", title="MAGGI Masala Instant Noodles 280g", brand="Maggi", price=60, mrp=60, quantity_text="280 g", normalized_quantity_value=280, normalized_quantity_unit="g", available=True, product_url="https://www.zepto.com/", raw_title="MAGGI Masala Instant Noodles 280g")],
        "amul butter": [ProductListing(provider="zepto", external_id="z-amul-500", title="Amul Salted Butter 500 GM", brand="Amul", price=290, mrp=300, quantity_text="500 g", normalized_quantity_value=500, normalized_quantity_unit="g", available=True, product_url="https://www.zepto.com/", raw_title="Amul Salted Butter 500 GM")],
    },
}


class MockProvider(GroceryProvider):
    def __init__(self, name: str):
        self.name = name
        self.location_verified = False

    async def establish_location(self, location: str) -> None:
        self.location_verified = location == "DTU"

    async def search(self, query: str, location: str) -> list[ProductListing]:
        if not self.location_verified:
            return []
        catalog = MOCK_PRODUCTS[self.name]
        return catalog.get(query.lower().strip(), [])
