from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from trip_fakes import BRASILIA, GOIANIA, flex

from gasprice.prices.domain import Fuel, State
from gasprice.trips.domain import (
    Coordinate,
    DrivingProfile,
    Efficiency,
    PriceTable,
    Route,
    TripPlan,
    TripRequest,
    apportion,
    distance_km,
    estimate_fuel,
)


def test_distance_between_brasilia_and_goiania() -> None:
    assert 170 < distance_km(BRASILIA, GOIANIA) < 180
    assert distance_km(BRASILIA, BRASILIA) == 0


def test_coordinates_are_validated() -> None:
    with pytest.raises(ValidationError):
        Coordinate(lat=91, lon=0)


def _by_longitude(point: Coordinate) -> State | None:
    if point.lon > -48:
        return State.DF
    return State.GO if point.lon > -50 else None


def test_apportion_splits_road_distance_by_line_share() -> None:
    line = tuple(Coordinate(lat=-16, lon=lon) for lon in (-47.0, -47.5, -48.0, -49.0, -51.0))
    shares = apportion(line, Decimal("400.0"), _by_longitude)
    assert shares == {State.DF: Decimal("100.0"), State.GO: Decimal("100.0"), None: Decimal("200.0")}


@given(st.lists(st.floats(min_value=-52, max_value=-46), min_size=2, max_size=30), st.integers(1, 5000))
def test_apportion_never_creates_or_loses_kilometres(lons: list[float], total: int) -> None:
    line = [Coordinate(lat=-16, lon=lon) for lon in lons]
    shares = apportion(line, Decimal(total), _by_longitude)
    assert sum(shares.values()) == Decimal(total)
    assert all(km > 0 for km in shares.values())


def test_apportion_of_a_point_goes_to_its_state() -> None:
    point = Coordinate(lat=-16, lon=-47)
    assert apportion((point, point), Decimal("3.0"), _by_longitude) == {State.DF: Decimal("3.0")}


def test_efficiency_by_profile() -> None:
    efficiency = Efficiency(city=Decimal(10), highway=Decimal(15))
    assert efficiency.at(DrivingProfile.CITY) == Decimal("10.00")
    assert efficiency.at(DrivingProfile.HIGHWAY) == Decimal("15.00")
    assert efficiency.at(DrivingProfile.MIXED) == Decimal("11.76")  # harmonic, not 12.25
    assert all(profile.label for profile in DrivingProfile)


def test_vehicle_name_and_flex() -> None:
    vehicle = flex()
    assert vehicle.name == "Fiat Argo Drive 1.0 (2025)"
    assert vehicle.is_flex
    assert not flex(efficiencies={Fuel.DIESEL_S10: Efficiency(city=Decimal(9), highway=Decimal(11))}).is_flex
    assert flex(year=None, version="").name == "Fiat Argo"


def test_estimate_prices_each_state_and_falls_back_to_the_mean() -> None:
    table = PriceTable(fuel=Fuel.GASOLINE, prices={State.DF: Decimal("6.000")}, mean=Decimal("6.500"))
    option = estimate_fuel(
        {State.DF: Decimal(100), State.GO: Decimal(50), None: Decimal(10)}, Decimal(10), table
    )
    assert option is not None
    assert option.liters == Decimal("16.0")
    assert option.cost == Decimal("60.00") + Decimal("32.50") + Decimal("6.50")
    assert [(part.state, part.estimated_price) for part in option.by_state] == [
        (State.DF, False),
        (State.GO, True),
        (None, True),
    ]
    assert option.uses_estimates
    assert option.cost_per_km == Decimal("0.619")


def test_estimate_needs_some_price() -> None:
    table = PriceTable(fuel=Fuel.CNG, prices={}, mean=None)
    assert estimate_fuel({State.DF: Decimal(1)}, Decimal(10), table) is None


def test_trip_request_needs_exactly_one_consumption() -> None:
    points = (BRASILIA, GOIANIA)
    with pytest.raises(ValidationError, match="não os dois"):
        TripRequest(points=points)
    with pytest.raises(ValidationError, match="não os dois"):
        TripRequest(points=points, vehicle_id="1", manual={Fuel.GASOLINE: Decimal(12)})
    with pytest.raises(ValidationError):
        TripRequest(points=(BRASILIA,), vehicle_id="1")
    assert TripRequest(points=points, manual={Fuel.GASOLINE: Decimal("12.345")}).manual[
        Fuel.GASOLINE
    ] == Decimal("12.35")


def test_plan_summaries() -> None:
    route = Route(distance_km=Decimal(100), duration_min=70, geometry=(BRASILIA, GOIANIA))
    table = PriceTable(fuel=Fuel.GASOLINE, prices={State.DF: Decimal(6)}, mean=Decimal(6))
    cheap = estimate_fuel({State.DF: Decimal(200)}, Decimal(20), table)
    dear = estimate_fuel({State.DF: Decimal(200)}, Decimal(10), table)
    assert cheap is not None
    assert dear is not None
    plan = TripPlan(
        route=route,
        km_by_state={State.DF: Decimal(200)},
        profile=DrivingProfile.MIXED,
        round_trip=True,
        vehicle=None,
        options=(cheap, dear),
    )
    assert plan.distance_km == Decimal(200)
    assert plan.duration_min == 140
    assert plan.cheapest == cheap
    assert plan.savings == Decimal("60.00")
    single = plan.model_copy(update={"options": (cheap,)})
    assert single.savings is None
    assert plan.model_copy(update={"options": ()}).cheapest is None
