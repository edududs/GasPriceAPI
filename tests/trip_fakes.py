from collections.abc import Sequence
from decimal import Decimal

from gasprice.prices.domain import Fuel, State
from gasprice.trips.application import NoRouteError, VehicleHarvest
from gasprice.trips.domain import Coordinate, Efficiency, PriceTable, Route, Vehicle, VehicleSource

BRASILIA = Coordinate(lat=-15.79, lon=-47.88)
GOIANIA = Coordinate(lat=-16.68, lon=-49.25)


def flex(vehicle_id: str = "1", **changes: object) -> Vehicle:
    return Vehicle.model_validate(
        {
            "id": vehicle_id,
            "source": VehicleSource.PBEV,
            "brand": "Fiat",
            "model": "Argo",
            "version": "Drive 1.0",
            "year": 2025,
            "efficiencies": {
                Fuel.GASOLINE: Efficiency(city=Decimal("13.0"), highway=Decimal("15.0")),
                Fuel.ETHANOL: Efficiency(city=Decimal("9.0"), highway=Decimal("10.5")),
            },
        }
        | changes
    )


class FixedRouter:
    """Two segments: the first half in DF, the second in GO (see `HalfLocator`)."""

    def __init__(self, km: str = "200.0", *, fail: Exception | None = None) -> None:
        self.km = Decimal(km)
        self.fail = fail
        self.calls: list[Sequence[Coordinate]] = []

    def route(self, points: Sequence[Coordinate]) -> Route:
        self.calls.append(points)
        if self.fail is not None:
            raise self.fail
        return Route(
            distance_km=self.km,
            duration_min=150,
            geometry=(
                Coordinate(lat=-16, lon=-47),
                Coordinate(lat=-16, lon=-48),
                Coordinate(lat=-16, lon=-49),
            ),
        )


class HalfLocator:
    def locate(self, point: Coordinate) -> State | None:
        return State.DF if point.lon > -48 else State.GO


class TablePrices:
    def __init__(self, tables: dict[Fuel, dict[State, str]]) -> None:
        self.tables = tables

    def table(self, fuel: Fuel) -> PriceTable:
        prices = {state: Decimal(price) for state, price in self.tables.get(fuel, {}).items()}
        mean = sum(prices.values(), Decimal(0)) / len(prices) if prices else None
        return PriceTable(fuel=fuel, prices=prices, mean=mean)


class MemoryCatalog:
    def __init__(self, vehicles: Sequence[Vehicle] = ()) -> None:
        self.vehicles = {vehicle.id: vehicle for vehicle in vehicles}
        self.replaced: list[tuple[VehicleSource, int]] = []

    def search(self, query: str, *, limit: int = 20) -> list[Vehicle]:
        return [vehicle for vehicle in self.vehicles.values() if query.lower() in vehicle.name.lower()][
            :limit
        ]

    def get(self, vehicle_id: str) -> Vehicle | None:
        return self.vehicles.get(vehicle_id)

    def replace(self, source: VehicleSource, vehicles: Sequence[Vehicle]) -> int:
        self.replaced.append((source, len(vehicles)))
        return len(vehicles)


class StubReader:
    source = VehicleSource.PBEV

    def __init__(self, harvest: VehicleHarvest) -> None:
        self.harvest = harvest

    def read(self) -> VehicleHarvest:
        return self.harvest


NO_ROUTE = NoRouteError("NoRoute")
