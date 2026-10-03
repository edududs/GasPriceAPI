from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Self

from pydantic import AfterValidator, Field, model_validator

from gasprice.prices.domain.fuel import Fuel
from gasprice.prices.domain.model import FrozenModel
from gasprice.prices.domain.source import Source
from gasprice.prices.domain.state import State

PRICE_PLACES = Decimal("0.001")
"""The ANP publishes prices to the tenth of a cent; storage keeps exactly that."""


def _to_places(value: Decimal) -> Decimal:
    return value.quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)


type Price = Annotated[Decimal, Field(gt=0, lt=10_000), AfterValidator(_to_places)]


class PriceReport(FrozenModel):
    """The price of one fuel in one state over one survey period, as one source reported it."""

    source: Source
    state: State
    fuel: Fuel
    period_start: date
    period_end: date
    average: Price
    minimum: Price | None = None
    maximum: Price | None = None
    stations: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.period_start > self.period_end:
            msg = "o período começa depois de terminar"
            raise ValueError(msg)
        if self.minimum is not None and self.minimum > self.average:
            msg = "preço mínimo acima da média"
            raise ValueError(msg)
        if self.maximum is not None and self.maximum < self.average:
            msg = "preço máximo abaixo da média"
            raise ValueError(msg)
        return self

    @property
    def key(self) -> tuple[State, Fuel]:
        return (self.state, self.fuel)


def preferred(reports: Iterable[PriceReport]) -> dict[tuple[State, Fuel], PriceReport]:
    """For each state and fuel, the report of the best-ranked source, newest period first within it."""
    chosen: dict[tuple[State, Fuel], PriceReport] = {}
    for report in reports:
        current = chosen.get(report.key)
        if current is None or _preference(report) < _preference(current):
            chosen[report.key] = report
    return chosen


def series(reports: Iterable[PriceReport]) -> list[PriceReport]:
    """One state's and fuel's reports as a time series from the best-ranked source present, oldest first.

    Mixing sources in one line would draw jumps that are differences in method, not in price.
    """
    collected = list(reports)
    if not collected:
        return []
    best = min(report.source.rank for report in collected)
    return sorted(
        (report for report in collected if report.source.rank == best),
        key=lambda report: report.period_end,
    )


def _preference(report: PriceReport) -> tuple[int, int]:
    return (report.source.rank, -report.period_end.toordinal())
