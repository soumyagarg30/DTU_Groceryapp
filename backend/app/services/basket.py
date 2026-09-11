"""Exact basket allocation over user-provided price snapshots, not checkout quotes."""
from decimal import Decimal, ROUND_HALF_UP
from itertools import product
from pydantic import BaseModel, Field


class BasketItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=1, le=99)
    blinkit: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    zepto: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)


class StoreFees(BaseModel):
    delivery: float = Field(default=25, ge=0, le=10000, allow_inf_nan=False)
    free_above: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    handling: float = Field(default=0, ge=0, le=10000, allow_inf_nan=False)


class BasketRequest(BaseModel):
    items: list[BasketItem] = Field(min_length=1, max_length=12)
    blinkit: StoreFees = Field(default_factory=StoreFees)
    zepto: StoreFees = Field(default_factory=StoreFees)


def cents(value: float) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def optimize_basket(request: BasketRequest):
    options = [[store for store in ('blinkit', 'zepto') if getattr(item, store) is not None] for item in request.items]
    if any(not choices for choices in options):
        raise ValueError('Every item needs at least one available store price.')

    def plan(assignment):
        stores = {}
        for store in ('blinkit', 'zepto'):
            indices = [i for i, selected in enumerate(assignment) if selected == store]
            if not indices:
                continue
            subtotal = sum(cents(getattr(request.items[i], store)) * request.items[i].quantity for i in indices)
            fees = getattr(request, store)
            delivery = 0 if fees.free_above is not None and subtotal >= cents(fees.free_above) else cents(fees.delivery)
            charge = delivery + cents(fees.handling)
            stores[store] = dict(subtotal=subtotal / 100, fees=charge / 100, total=(subtotal + charge) / 100, item_indices=indices)
        total = sum(cents(store['total']) for store in stores.values())
        return dict(total=total / 100, stores=stores, assignment=list(assignment))

    best = min((plan(a) for a in product(*options)), key=lambda p: (p['total'], len(p['stores'])))
    single = {store: plan([store] * len(options)) if all(store in o for o in options) else None for store in ('blinkit', 'zepto')}
    baseline = min((p['total'] for p in single.values() if p), default=None)
    return dict(best=best, single_store=single, savings_vs_single=None if baseline is None else round(baseline - best['total'], 2), estimated=True)
