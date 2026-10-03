from datetime import UTC, datetime, timedelta

from fakes import SATURDAY, FixedClock, MemoryPriceRepository, StubSource, report

from gasprice.prices.application import (
    CollectPrices,
    GetBoard,
    GetHealth,
    GetHistory,
    GetLatest,
    GetStateOverview,
)
from gasprice.prices.domain import CollectionRun, Fuel, Source, State


def test_collect_saves_and_records_a_successful_run() -> None:
    repository, clock = MemoryPriceRepository(), FixedClock()
    run = CollectPrices(repository, clock)(
        StubSource([report(), report(state=State.RJ)], skipped=["linha 9: x"])
    )
    assert run.succeeded
    assert (run.written, run.skipped) == (2, 1)
    assert repository.runs == [run]
    assert len(repository.reports) == 2


def test_collect_records_an_unreachable_source_as_failed() -> None:
    repository = MemoryPriceRepository()
    run = CollectPrices(repository, FixedClock())(StubSource(fail="HTTP 503"))
    assert not run.succeeded
    assert run.error == "HTTP 503"
    assert repository.runs == [run]
    assert not repository.reports


def test_collect_treats_an_empty_harvest_as_a_failure() -> None:
    """A source that answers with nothing recognisable usually changed its layout."""
    repository = MemoryPriceRepository()
    run = CollectPrices(repository, FixedClock())(StubSource(skipped=[f"linha {n}: ?" for n in range(15)]))
    assert not run.succeeded
    assert run.error is not None
    assert "15 linhas ignoradas" in run.error


def test_latest_orders_by_state_then_fuel() -> None:
    repository = MemoryPriceRepository()
    repository.save_all(
        [report(state=State.SP, fuel=Fuel.LPG, average="110"), report(state=State.SP), report(state=State.AC)]
    )
    latest = GetLatest(repository)()
    assert [(item.state, item.fuel) for item in latest] == [
        (State.AC, Fuel.GASOLINE),
        (State.SP, Fuel.GASOLINE),
        (State.SP, Fuel.LPG),
    ]
    assert GetBoard(repository)(Fuel.GASOLINE).cheapest is not None


def test_history_and_overview() -> None:
    repository, clock = MemoryPriceRepository(), FixedClock()
    weeks = [report(end=SATURDAY - timedelta(weeks=n), average=f"6.{n}00") for n in range(4)]
    repository.save_all([*weeks, report(fuel=Fuel.ETHANOL, average="4.1")])
    assert [item.period_end for item in GetHistory(repository)(State.SP, Fuel.GASOLINE)] == sorted(
        item.period_end for item in weeks
    )
    overview = GetStateOverview(repository, clock)(State.SP, Fuel.GASOLINE, weeks=2)
    assert [item.fuel for item in overview.current] == [Fuel.GASOLINE, Fuel.ETHANOL]
    assert overview.selected == weeks[0]
    assert len(overview.history) == 2
    assert GetStateOverview(repository, clock)(State.SP, Fuel.CNG).selected is None


def _run(source: Source, finished: datetime, error: str | None = None) -> CollectionRun:
    return CollectionRun(source=source, started_at=finished, finished_at=finished, error=error)


def test_health_needs_a_recent_real_collection() -> None:
    clock = FixedClock(datetime(2026, 9, 28, tzinfo=UTC))
    repository = MemoryPriceRepository()
    assert not GetHealth(repository, clock)().healthy

    repository.record_run(_run(Source.DEMO, clock.at))
    assert not GetHealth(repository, clock)().healthy, "demo data never makes the service healthy"

    repository.record_run(_run(Source.ANP, clock.at - timedelta(days=3)))
    repository.record_run(_run(Source.ANP, clock.at, error="HTTP 500"))
    health = GetHealth(repository, clock, max_age_days=15)()
    assert health.healthy
    assert health.last_run is not None
    assert health.last_run.error == "HTTP 500"

    late = FixedClock(datetime(2026, 10, 20, tzinfo=UTC))
    assert not GetHealth(repository, late, max_age_days=15)().healthy
