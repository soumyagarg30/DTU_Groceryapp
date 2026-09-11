from dataclasses import dataclass

from ..models.product import ProductListing
from .normalization import extract_quantity


@dataclass(frozen=True)
class UnitPrice:
    unit_price: float
    unit_price_basis: str


def calculate_unit_price(listing: ProductListing) -> UnitPrice | None:
    quantity = extract_quantity(listing.quantity_text or listing.title)
    if not quantity.total_value or not quantity.unit or quantity.total_value <= 0:
        return None
    if quantity.unit == "g":
        basis_value, basis = 100, "100 g"
    elif quantity.unit == "ml":
        basis_value, basis = 100, "100 ml"
    elif quantity.unit == "pcs":
        basis_value, basis = 1, "piece"
    else:
        return None
    return UnitPrice(round(listing.price / quantity.total_value * basis_value, 2), basis)


def calculate_savings_percentage(price_a: float, price_b: float) -> float:
    higher = max(price_a, price_b)
    if higher <= 0:
        return 0.0
    return round(abs(price_a - price_b) / higher * 100, 1)
