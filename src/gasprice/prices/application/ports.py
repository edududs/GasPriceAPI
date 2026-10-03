from collections.abc import Collection, Sequence
from datetime import date, datetime
from typing import Protocol

from gasprice.prices.domain import CollectionRun, Fuel, PriceReport, Source, State
from gasprice.prices.domain.model import FrozenModel


class SourceUnavailableError(Exception):
    """The source could not be read at all: network, HTTP status, a file that is not what it should be."""


class Harvest(FrozenModel):
    """What one read of a source produced. `skipped` says, line by line, what was left out and why."""

    reports: tuple[PriceReport, ...]
    skipped: tuple[str, ...] = ()


class PriceSource(Protocol):
    @property
    def source(self) -> Source: ...

    def fetch(self) -> Harvest:
        """Read the source once. Raises SourceUnavailableError when nothing could be read."""
        ...


class PriceRepository(Protocol):
    def save_all(self, reports: Sequence[PriceReport]) -> int:
        """Create or replace each report by (source, state, fuel, period_end), all or nothing.

        Returns how many were written.
        """
        ...

    def latest(self, *, fuel: Fuel | None = None, state: State | None = None) -> list[PriceReport]:
        """For each source, state and fuel matching the filters, the report of the newest period."""
        ...

    def history(self, state: State, fuel: Fuel, *, since: date | None = None) -> list[PriceReport]:
        """Every report for the state and fuel from every source, ending on or after `since`."""
        ...

    def record_run(self, run: CollectionRun) -> None: ...

    def last_run(
        self, *, succeeded: bool | None = None, sources: Collection[Source] | None = None
    ) -> CollectionRun | None:
        """The run that finished last, optionally only among those that did or did not succeed, or
        among the given sources."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...
