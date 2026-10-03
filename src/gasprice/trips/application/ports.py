from collections.abc import Sequence
from typing import Protocol

from gasprice.prices.domain import Fuel, State
from gasprice.prices.domain.model import FrozenModel
from gasprice.trips.domain import Coordinate, PriceTable, Route, Vehicle, VehicleSource


class RouteUnavailableError(Exception):
    """The routing service could not be reached or answered with an error."""


class NoRouteError(Exception):
    """The service answered, but there is no road route between the points."""


class GeocoderUnavailableError(Exception):
    pass


class VehicleSourceError(Exception):
    """A catalog file could not be read at all."""


class Place(FrozenModel):
    name: str
    coordinate: Coordinate


class VehicleHarvest(FrozenModel):
    vehicles: tuple[Vehicle, ...]
    skipped: tuple[str, ...] = ()


class RouteProvider(Protocol):
    def route(self, points: Sequence[Coordinate]) -> Route:
        """Driving route through the points in order. Raises NoRouteError or RouteUnavailableError."""
        ...


class Geocoder(Protocol):
    def search(self, query: str) -> list[Place]:
        """Places in Brazil matching the text, best first. Raises GeocoderUnavailableError."""
        ...


class StateLocator(Protocol):
    def locate(self, point: Coordinate) -> State | None: ...


class FuelPrices(Protocol):
    def table(self, fuel: Fuel) -> PriceTable: ...


class VehicleCatalog(Protocol):
    def search(self, query: str, *, limit: int = 20) -> list[Vehicle]:
        """Vehicles whose brand, model or version contain every word of the query, accents ignored."""
        ...

    def get(self, vehicle_id: str) -> Vehicle | None: ...

    def replace(self, source: VehicleSource, vehicles: Sequence[Vehicle]) -> int:
        """Make `vehicles` the whole catalog of `source`, all or nothing. Returns how many were stored."""
        ...


class VehicleSourceReader(Protocol):
    @property
    def source(self) -> VehicleSource: ...

    def read(self) -> VehicleHarvest:
        """Raises VehicleSourceError when nothing could be read."""
        ...
