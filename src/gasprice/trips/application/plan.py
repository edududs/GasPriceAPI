import logging

from gasprice.prices.domain import Fuel
from gasprice.trips.application.ports import (
    FuelPrices,
    RouteProvider,
    StateLocator,
    VehicleCatalog,
    VehicleHarvest,
    VehicleSourceReader,
)
from gasprice.trips.domain import (
    FuelOption,
    TripError,
    TripPlan,
    TripRequest,
    Vehicle,
    apportion,
    estimate_fuel,
)

logger = logging.getLogger(__name__)


class PlanTrip:
    """Route the points, split the distance by state, and price every fuel the vehicle takes."""

    def __init__(
        self, router: RouteProvider, locator: StateLocator, prices: FuelPrices, vehicles: VehicleCatalog
    ) -> None:
        self._router = router
        self._locator = locator
        self._prices = prices
        self._vehicles = vehicles

    def __call__(self, request: TripRequest) -> TripPlan:
        vehicle = self._vehicle(request)
        consumption = (
            {fuel: efficiency.at(request.profile) for fuel, efficiency in vehicle.efficiencies.items()}
            if vehicle is not None
            else dict(request.manual)
        )
        route = self._router.route(request.points)
        km_by_state = apportion(route.geometry, route.distance_km, self._locator.locate)
        if request.round_trip:
            km_by_state = {state: km * 2 for state, km in km_by_state.items()}

        options: list[FuelOption] = []
        unpriced: list[Fuel] = []
        for fuel, km_per_liter in consumption.items():
            option = estimate_fuel(km_by_state, km_per_liter, self._prices.table(fuel))
            if option is None:
                unpriced.append(fuel)
            else:
                options.append(option)
        return TripPlan(
            route=route,
            km_by_state=km_by_state,
            profile=request.profile,
            round_trip=request.round_trip,
            vehicle=vehicle,
            options=tuple(sorted(options, key=lambda option: option.cost)),
            unpriced=tuple(unpriced),
        )

    def _vehicle(self, request: TripRequest) -> Vehicle | None:
        if request.vehicle_id is None:
            return None
        vehicle = self._vehicles.get(request.vehicle_id)
        if vehicle is None:
            msg = "veículo não encontrado no catálogo"
            raise TripError(msg)
        return vehicle


class ImportVehicles:
    """Replace one source's catalog with what the reader found. An empty read changes nothing."""

    def __init__(self, catalog: VehicleCatalog) -> None:
        self._catalog = catalog

    def __call__(self, reader: VehicleSourceReader) -> VehicleHarvest:
        harvest = reader.read()
        for reason in harvest.skipped[:10]:
            logger.warning("%s: ignorado: %s", reader.source, reason)
        if not harvest.vehicles:
            msg = f"nenhum veículo reconhecido ({len(harvest.skipped)} linhas ignoradas)"
            raise TripError(msg)
        self._catalog.replace(reader.source, harvest.vehicles)
        return harvest
