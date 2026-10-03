from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Self

from gasprice.prices.domain.fuel import Fuel
from gasprice.prices.domain.model import FrozenModel
from gasprice.prices.domain.report import PRICE_PLACES, PriceReport, preferred
from gasprice.prices.domain.source import Source


class Board(FrozenModel):
    """One fuel across the country: each state's current price, cheapest first."""

    fuel: Fuel
    entries: tuple[PriceReport, ...]

    @classmethod
    def of(cls, fuel: Fuel, reports: Iterable[PriceReport]) -> Self:
        chosen = [report for report in preferred(reports).values() if report.fuel == fuel]
        return cls(fuel=fuel, entries=tuple(sorted(chosen, key=lambda r: (r.average, r.state))))

    @property
    def is_empty(self) -> bool:
        return not self.entries

    @property
    def cheapest(self) -> PriceReport | None:
        return self.entries[0] if self.entries else None

    @property
    def priciest(self) -> PriceReport | None:
        return self.entries[-1] if self.entries else None

    @property
    def mean(self) -> Decimal | None:
        """Plain mean across states. Not weighted by stations: it answers "how does my state compare"."""
        if not self.entries:
            return None
        total = sum((entry.average for entry in self.entries), Decimal(0))
        return (total / len(self.entries)).quantize(PRICE_PLACES)

    @property
    def latest_period(self) -> date | None:
        return max((entry.period_end for entry in self.entries), default=None)

    @property
    def sources(self) -> frozenset[Source]:
        return frozenset(entry.source for entry in self.entries)
