"""Synthetic prices so the site has something to show before the first real collection.

Deterministic: the same seed and day always produce the same numbers. Stored as the `demo` source,
which ranks last, so the first ANP collection replaces it everywhere without deleting anything.
"""

import random
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

from gasprice.prices.application import Harvest
from gasprice.prices.domain import Fuel, PriceReport, Region, Source, State

BASE_PRICE = {
    Fuel.GASOLINE: 6.30,
    Fuel.GASOLINE_PREMIUM: 6.55,
    Fuel.ETHANOL: 4.45,
    Fuel.DIESEL: 6.05,
    Fuel.DIESEL_S10: 6.15,
    Fuel.CNG: 4.95,
    Fuel.LPG: 108.0,
}
REGION_FACTOR = {
    Region.NORTH: 1.07,
    Region.NORTHEAST: 1.02,
    Region.MIDWEST: 1.00,
    Region.SOUTHEAST: 0.97,
    Region.SOUTH: 0.99,
}
WEEKLY_DRIFT = 0.008


class DemoSource:
    source = Source.DEMO

    def __init__(self, *, today: Callable[[], date], weeks: int = 52, seed: int = 42) -> None:
        self._today = today
        self._weeks = weeks
        self._seed = seed

    def fetch(self) -> Harvest:
        rng = random.Random(self._seed)  # noqa: S311  demo numbers, not security
        last_saturday = self._today() - timedelta(days=(self._today().weekday() + 2) % 7)
        reports: list[PriceReport] = []
        for state in State:
            for fuel, base in BASE_PRICE.items():
                price = base * REGION_FACTOR[state.region] * rng.uniform(0.95, 1.05)
                for week in range(self._weeks, 0, -1):
                    price *= 1 + rng.uniform(-WEEKLY_DRIFT, WEEKLY_DRIFT * 1.1)
                    end = last_saturday - timedelta(weeks=week - 1)
                    average = Decimal(f"{price:.3f}")
                    reports.append(
                        PriceReport(
                            source=Source.DEMO,
                            state=state,
                            fuel=fuel,
                            period_start=end - timedelta(days=6),
                            period_end=end,
                            average=average,
                            minimum=Decimal(f"{price * 0.93:.3f}"),
                            maximum=Decimal(f"{price * 1.08:.3f}"),
                            stations=rng.randint(40, 600),
                        )
                    )
        return Harvest(reports=tuple(reports))
