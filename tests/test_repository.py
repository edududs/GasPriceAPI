"""The port's contract, run against every adapter (see the `repository` fixture)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fakes import SATURDAY, report

from gasprice.prices.application import PriceRepository
from gasprice.prices.domain import CollectionRun, Fuel, PriceReport, Source, State


def test_save_is_an_upsert_by_period(repository: PriceRepository) -> None:
    assert repository.save_all([report(average="6.000")]) == 1
    repository.save_all([report(average="6.100", stations=10)])
    (stored,) = repository.history(State.SP, Fuel.GASOLINE)
    assert (stored.average, stored.stations) == (Decimal("6.100"), 10)


def test_round_trip_keeps_every_field(repository: PriceRepository) -> None:
    original = report(average="6.199", minimum="5.500", maximum="7.250", stations=321)
    repository.save_all([original])
    assert repository.history(State.SP, Fuel.GASOLINE) == [original]


def test_latest_is_the_newest_period_per_source_state_and_fuel(repository: PriceRepository) -> None:
    old, new = report(end=SATURDAY - timedelta(weeks=1)), report(end=SATURDAY)
    petrobras = report(source=Source.PETROBRAS, end=date(2026, 9, 28))
    ethanol = report(fuel=Fuel.ETHANOL, average="4.0")
    rio = report(state=State.RJ)
    repository.save_all([old, new, petrobras, ethanol, rio])

    def ordered(items: list[PriceReport]) -> list[PriceReport]:
        return sorted(items, key=lambda item: (item.source, item.state, item.fuel))

    assert ordered(repository.latest()) == ordered([new, petrobras, ethanol, rio])
    assert ordered(repository.latest(fuel=Fuel.GASOLINE, state=State.SP)) == ordered([new, petrobras])
    assert repository.latest(fuel=Fuel.CNG) == []


def test_history_filters_and_orders(repository: PriceRepository) -> None:
    weeks = [report(end=SATURDAY - timedelta(weeks=n)) for n in range(3)]
    repository.save_all([*weeks, report(state=State.RJ)])
    since = SATURDAY - timedelta(weeks=1)
    assert [item.period_end for item in repository.history(State.SP, Fuel.GASOLINE, since=since)] == [
        since,
        SATURDAY,
    ]


@pytest.mark.parametrize("sources", [None, {Source.ANP}])
def test_runs(repository: PriceRepository, sources: set[Source] | None) -> None:
    at = datetime(2026, 9, 28, 12, tzinfo=UTC)
    ok = CollectionRun(source=Source.ANP, started_at=at, finished_at=at, written=5)
    failed = CollectionRun(source=Source.ANP, started_at=at, finished_at=at + timedelta(hours=1), error="x")
    demo = CollectionRun(source=Source.DEMO, started_at=at, finished_at=at + timedelta(hours=2))
    assert repository.last_run() is None
    for run in (ok, failed, demo):
        repository.record_run(run)
    assert repository.last_run(sources=sources) == (failed if sources else demo)
    assert repository.last_run(succeeded=True, sources=sources) == (ok if sources else demo)
    assert repository.last_run(succeeded=False) == failed
