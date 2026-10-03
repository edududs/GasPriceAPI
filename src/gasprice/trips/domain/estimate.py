from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from gasprice.prices.domain import Fuel, State
from gasprice.prices.domain.model import FrozenModel

CENTS = Decimal("0.01")
TENTH = Decimal("0.1")


class PriceTable(FrozenModel):
    """Current price of one fuel per state, plus the mean that stands in for states without one."""

    fuel: Fuel
    prices: dict[State, Decimal]
    mean: Decimal | None
    period_end: date | None = None


class StateCost(FrozenModel):
    state: State | None
    km: Decimal
    liters: Decimal
    price: Decimal
    cost: Decimal
    estimated_price: bool
    """The state had no price for this fuel, so the mean across states was used."""


class FuelOption(FrozenModel):
    fuel: Fuel
    km_per_liter: Decimal
    liters: Decimal
    cost: Decimal
    by_state: tuple[StateCost, ...]
    period_end: date | None

    @property
    def cost_per_km(self) -> Decimal:
        km = sum((part.km for part in self.by_state), Decimal(0))
        return (self.cost / km).quantize(Decimal("0.001")) if km else Decimal(0)

    @property
    def uses_estimates(self) -> bool:
        return any(part.estimated_price for part in self.by_state)


def estimate_fuel(
    km_by_state: Mapping[State | None, Decimal], km_per_liter: Decimal, table: PriceTable
) -> FuelOption | None:
    """Litres and cost of driving each state's share at its own price. None when no price is known at all."""
    if table.mean is None:
        return None
    parts: list[StateCost] = []
    for state, km in sorted(km_by_state.items(), key=lambda item: -item[1]):
        price = table.prices.get(state) if state is not None else None
        estimated = price is None
        unit_price = table.mean if price is None else price
        liters = km / km_per_liter
        parts.append(
            StateCost(
                state=state,
                km=km,
                liters=liters.quantize(TENTH, rounding=ROUND_HALF_UP),
                price=unit_price,
                cost=(liters * unit_price).quantize(CENTS, rounding=ROUND_HALF_UP),
                estimated_price=estimated,
            )
        )
    total_liters = sum((km for km in km_by_state.values()), Decimal(0)) / km_per_liter
    return FuelOption(
        fuel=table.fuel,
        km_per_liter=km_per_liter,
        liters=total_liters.quantize(TENTH, rounding=ROUND_HALF_UP),
        cost=sum((part.cost for part in parts), Decimal(0)),
        by_state=tuple(parts),
        period_end=table.period_end,
    )
