from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any, Literal


ProviderName = Literal["blinkit", "zepto"]


class ProductListing(BaseModel):
    provider: ProviderName
    external_id: str | None = None
    title: str
    brand: str | None = None
    price: float
    mrp: float | None = None
    currency: str = "INR"
    quantity_text: str | None = None
    normalized_quantity_value: float | None = None
    normalized_quantity_unit: Literal["g", "ml", "pcs"] | None = None
    pack_count: int | None = None
    available: bool
    product_url: str | None = None
    image_url: str | None = None
    raw_title: str | None = None
    raw_card_text: str | None = None
    fetched_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
