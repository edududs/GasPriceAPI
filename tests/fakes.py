"""In-memory doubles of the ports. `MemoryPriceRepository` passes the same contract as the Django one."""

from collections.abc import Collection, Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from gasprice.prices.application import Harvest, SourceUnavailableError
from gasprice.prices.domain import CollectionRun, Fuel, PriceReport, Source, State

SATURDAY = date(2026, 9, 26)


def report(  # noqa: PLR0913  a factory: every field is a knob
    *,
    state: State = State.SP,
    fuel: Fuel = Fuel.GASOLINE,
    source: Source = Source.ANP,
    end: date = SATURDAY,
    average: str = "6.199",
    minimum: str | None = None,
    maximum: str | None = None,
    stations: int | None = None,
) -> PriceReport:
    return PriceReport(
        source=source,
        state=state,
        fuel=fuel,
        period_start=end - timedelta(days=6),
        period_end=end,
        average=Decimal(average),
        minimum=Decimal(minimum) if minimum else None,
        maximum=Decimal(maximum) if maximum else None,
        stations=stations,
    )


class MemoryPriceRepository:
    def __init__(self) -> None:
        self.reports: dict[tuple[Source, State, Fuel, date], PriceReport] = {}
        self.runs: list[CollectionRun] = []

    def save_all(self, reports: Sequence[PriceReport]) -> int:
        for item in reports:
            self.reports[(item.source, item.state, item.fuel, item.period_end)] = item
        return len(reports)

    def latest(self, *, fuel: Fuel | None = None, state: State | None = None) -> list[PriceReport]:
        newest: dict[tuple[Source, State, Fuel], PriceReport] = {}
        for item in self.reports.values():
            if (fuel is None or item.fuel == fuel) and (state is None or item.state == state):
                key = (item.source, item.state, item.fuel)
                if key not in newest or newest[key].period_end < item.period_end:
                    newest[key] = item
        return list(newest.values())

    def history(self, state: State, fuel: Fuel, *, since: date | None = None) -> list[PriceReport]:
        return sorted(
            (
                item
                for item in self.reports.values()
                if item.state == state and item.fuel == fuel and (since is None or item.period_end >= since)
            ),
            key=lambda item: item.period_end,
        )

    def record_run(self, run: CollectionRun) -> None:
        self.runs.append(run)

    def last_run(
        self, *, succeeded: bool | None = None, sources: Collection[Source] | None = None
    ) -> CollectionRun | None:
        matching = [
            (order, run)
            for order, run in enumerate(self.runs)
            if (succeeded is None or run.succeeded == succeeded)
            and (sources is None or run.source in sources)
        ]
        # Same tie-break as the database: among runs that finished together, the one recorded last.
        latest = max(matching, key=lambda item: (item[1].finished_at, item[0]), default=None)
        return latest[1] if latest else None


class FixedClock:
    def __init__(self, at: datetime = datetime(2026, 9, 28, 12, tzinfo=UTC)) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


class StubSource:
    def __init__(
        self, reports: Iterable[PriceReport] = (), *, skipped: Iterable[str] = (), fail: str | None = None
    ) -> None:
        self.source = Source.ANP
        self._harvest = Harvest(reports=tuple(reports), skipped=tuple(skipped))
        self._fail = fail

    def fetch(self) -> Harvest:
        if self._fail is not None:
            raise SourceUnavailableError(self._fail)
        return self._harvest
