from decimal import Decimal

import pytest
from trip_fakes import (
    BRASILIA,
    GOIANIA,
    NO_ROUTE,
    FixedRouter,
    HalfLocator,
    MemoryCatalog,
    StubReader,
    TablePrices,
    flex,
)

from gasprice.prices.domain import Fuel, State
from gasprice.trips.application import ImportVehicles, NoRouteError, PlanTrip, VehicleHarvest
from gasprice.trips.domain import DrivingProfile, TripError, TripRequest, VehicleSource

PRICES = TablePrices(
    {
        Fuel.GASOLINE: {State.DF: "6.000", State.GO: "6.400"},
        Fuel.ETHANOL: {State.DF: "4.000", State.GO: "4.200"},
    }
)


def _plan(router: FixedRouter | None = None, catalog: MemoryCatalog | None = None) -> PlanTrip:
    return PlanTrip(router or FixedRouter(), HalfLocator(), PRICES, catalog or MemoryCatalog([flex()]))


def test_catalog_vehicle_is_priced_for_every_fuel_cheapest_first() -> None:
    plan = _plan()(TripRequest(points=(BRASILIA, GOIANIA), vehicle_id="1", profile=DrivingProfile.HIGHWAY))
    assert plan.km_by_state == {State.DF: Decimal("100.0"), State.GO: Decimal("100.0")}
    assert [option.fuel for option in plan.options] == [Fuel.ETHANOL, Fuel.GASOLINE]
    gasoline = plan.options[1]
    assert gasoline.km_per_liter == Decimal("15.00")
    assert gasoline.cost == Decimal("40.00") + Decimal("42.67")
    assert plan.vehicle == flex()


def test_round_trip_doubles_every_state() -> None:
    request = TripRequest(points=(BRASILIA, GOIANIA), manual={Fuel.GASOLINE: Decimal(10)}, round_trip=True)
    plan = _plan()(request)
    assert plan.km_by_state == {State.DF: Decimal("200.0"), State.GO: Decimal("200.0")}
    assert plan.vehicle is None


def test_fuels_without_any_price_are_reported() -> None:
    request = TripRequest(
        points=(BRASILIA, GOIANIA), manual={Fuel.GASOLINE: Decimal(10), Fuel.DIESEL_S10: Decimal(9)}
    )
    plan = _plan()(request)
    assert [option.fuel for option in plan.options] == [Fuel.GASOLINE]
    assert plan.unpriced == (Fuel.DIESEL_S10,)


def test_unknown_vehicle_and_routing_errors_propagate() -> None:
    with pytest.raises(TripError, match="não encontrado"):
        _plan()(TripRequest(points=(BRASILIA, GOIANIA), vehicle_id="99"))
    router = FixedRouter(fail=NO_ROUTE)
    with pytest.raises(NoRouteError):
        _plan(router)(TripRequest(points=(BRASILIA, GOIANIA), vehicle_id="1"))
    assert router.calls == [(BRASILIA, GOIANIA)]


def test_import_replaces_the_source_catalog() -> None:
    catalog = MemoryCatalog()
    harvest = ImportVehicles(catalog)(StubReader(VehicleHarvest(vehicles=(flex(),), skipped=("linha 9: x",))))
    assert len(harvest.vehicles) == 1
    assert catalog.replaced == [(VehicleSource.PBEV, 1)]


def test_import_of_nothing_changes_nothing() -> None:
    catalog = MemoryCatalog()
    with pytest.raises(TripError, match="nenhum veículo"):
        ImportVehicles(catalog)(StubReader(VehicleHarvest(vehicles=(), skipped=("a", "b"))))
    assert catalog.replaced == []
