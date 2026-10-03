from datetime import date, timedelta

from gasprice.prices.application.ports import Clock, PriceRepository
from gasprice.prices.domain import Board, CollectionRun, Fuel, PriceReport, Source, State, preferred, series
from gasprice.prices.domain.model import FrozenModel


class StateOverview(FrozenModel):
    state: State
    fuel: Fuel
    current: tuple[PriceReport, ...]
    """The state's latest price for every fuel it has, in the order fuels are declared."""
    history: tuple[PriceReport, ...]
    """The chosen fuel over time, oldest first, from one source."""

    @property
    def selected(self) -> PriceReport | None:
        return next((report for report in self.current if report.fuel == self.fuel), None)


class Health(FrozenModel):
    healthy: bool
    last_success: CollectionRun | None
    last_run: CollectionRun | None
    max_age_days: int


class GetBoard:
    def __init__(self, repository: PriceRepository) -> None:
        self._repository = repository

    def __call__(self, fuel: Fuel) -> Board:
        return Board.of(fuel, self._repository.latest(fuel=fuel))


class GetLatest:
    def __init__(self, repository: PriceRepository) -> None:
        self._repository = repository

    def __call__(self, *, fuel: Fuel | None = None, state: State | None = None) -> list[PriceReport]:
        """The preferred report per state and fuel, by state then fuel declaration order."""
        chosen = preferred(self._repository.latest(fuel=fuel, state=state))
        order = {fuel: index for index, fuel in enumerate(Fuel)}
        return sorted(chosen.values(), key=lambda report: (report.state, order[report.fuel]))


class GetHistory:
    def __init__(self, repository: PriceRepository) -> None:
        self._repository = repository

    def __call__(self, state: State, fuel: Fuel, *, since: date | None = None) -> list[PriceReport]:
        return series(self._repository.history(state, fuel, since=since))


class GetStateOverview:
    def __init__(self, repository: PriceRepository, clock: Clock) -> None:
        self._latest = GetLatest(repository)
        self._history = GetHistory(repository)
        self._clock = clock

    def __call__(self, state: State, fuel: Fuel, *, weeks: int = 52) -> StateOverview:
        since = self._clock.now().date() - timedelta(weeks=weeks)
        return StateOverview(
            state=state,
            fuel=fuel,
            current=tuple(self._latest(state=state)),
            history=tuple(self._history(state, fuel, since=since)),
        )


REAL_SOURCES = frozenset(source for source in Source if source is not Source.DEMO)


class GetHealth:
    """Healthy means a real source was collected recently enough: demo data never counts. The ANP
    publishes weekly, so the default allows one missed week before raising the alarm."""

    def __init__(self, repository: PriceRepository, clock: Clock, *, max_age_days: int = 15) -> None:
        self._repository = repository
        self._clock = clock
        self._max_age = timedelta(days=max_age_days)

    def __call__(self) -> Health:
        last_success = self._repository.last_run(succeeded=True, sources=REAL_SOURCES)
        healthy = last_success is not None and self._clock.now() - last_success.finished_at <= self._max_age
        return Health(
            healthy=healthy,
            last_success=last_success,
            last_run=self._repository.last_run(),
            max_age_days=self._max_age.days,
        )
