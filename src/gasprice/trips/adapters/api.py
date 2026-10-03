"""Trips under /api/v1: plan a trip, search vehicles and places. Schemas are the contract."""

from decimal import Decimal
from http import HTTPStatus
from typing import Self

from django.http import HttpRequest
from ninja import Field, Router, Schema
from ninja.errors import HttpError
from pydantic import ValidationError

from gasprice.prices.domain import Fuel, State
from gasprice.trips.adapters.composition import catalog, geocoder, plan_trip
from gasprice.trips.application import GeocoderUnavailableError, NoRouteError, RouteUnavailableError
from gasprice.trips.domain import (
    Coordinate,
    DrivingProfile,
    FuelOption,
    TripError,
    TripPlan,
    TripRequest,
    Vehicle,
)

router = Router(tags=["trips"])


class PointIn(Schema):
    lat: float
    lon: float


class TripIn(Schema):
    points: list[PointIn] = Field(..., min_length=2, max_length=10)
    profile: DrivingProfile = DrivingProfile.MIXED
    round_trip: bool = False
    vehicle_id: str | None = None
    manual: dict[Fuel, Decimal] = Field(default_factory=dict[Fuel, Decimal])


class EfficiencyOut(Schema):
    fuel: Fuel
    city: Decimal
    highway: Decimal


class VehicleOut(Schema):
    id: str
    name: str
    source: str
    efficiencies: list[EfficiencyOut]

    @classmethod
    def of(cls, vehicle: Vehicle) -> Self:
        return cls(
            id=vehicle.id,
            name=vehicle.name,
            source=vehicle.source.value,
            efficiencies=[
                EfficiencyOut(fuel=fuel, city=value.city, highway=value.highway)
                for fuel, value in vehicle.efficiencies.items()
            ],
        )


class StateKmOut(Schema):
    state: State | None
    km: Decimal


class StateCostOut(StateKmOut):
    liters: Decimal
    price: Decimal
    cost: Decimal
    estimated_price: bool


class OptionOut(Schema):
    fuel: Fuel
    km_per_liter: Decimal
    liters: Decimal
    cost: Decimal
    by_state: list[StateCostOut]

    @classmethod
    def of(cls, option: FuelOption) -> Self:
        return cls(
            fuel=option.fuel,
            km_per_liter=option.km_per_liter,
            liters=option.liters,
            cost=option.cost,
            by_state=[StateCostOut(**part.model_dump()) for part in option.by_state],
        )


class TripOut(Schema):
    distance_km: Decimal
    duration_min: int
    approximate: bool
    round_trip: bool
    vehicle: VehicleOut | None
    km_by_state: list[StateKmOut]
    options: list[OptionOut]
    unpriced: list[Fuel]
    geometry: list[tuple[float, float]]

    @classmethod
    def of(cls, plan: TripPlan) -> Self:
        return cls(
            distance_km=plan.distance_km,
            duration_min=plan.duration_min,
            approximate=plan.route.approximate,
            round_trip=plan.round_trip,
            vehicle=VehicleOut.of(plan.vehicle) if plan.vehicle else None,
            km_by_state=[StateKmOut(state=state, km=km) for state, km in plan.km_by_state.items()],
            options=[OptionOut.of(option) for option in plan.options],
            unpriced=list(plan.unpriced),
            geometry=[(point.lat, point.lon) for point in plan.route.geometry],
        )


class PlaceOut(Schema):
    name: str
    lat: float
    lon: float


class ErrorOut(Schema):
    detail: str


def run_plan(request: TripRequest) -> TripPlan:
    """Plan, with every failure translated to the status the HTML views and the API both use."""
    try:
        return plan_trip()(request)
    except (TripError, NoRouteError) as error:
        raise HttpError(HTTPStatus.UNPROCESSABLE_ENTITY, str(error)) from error
    except RouteUnavailableError as error:
        raise HttpError(HTTPStatus.SERVICE_UNAVAILABLE, f"roteador indisponível: {error}") from error


@router.post(
    "/trips/estimate",
    response={200: TripOut, 422: ErrorOut, 503: ErrorOut},
    summary="Custo de combustível de uma viagem",
)
def estimate(request: HttpRequest, payload: TripIn) -> TripOut:
    """Rota pelos pontos, km em cada estado e custo para cada combustível do veículo, mais barato primeiro."""
    try:
        trip = TripRequest(
            points=tuple(Coordinate(lat=point.lat, lon=point.lon) for point in payload.points),
            profile=payload.profile,
            round_trip=payload.round_trip,
            vehicle_id=payload.vehicle_id,
            manual=payload.manual,
        )
    except ValidationError as error:
        raise HttpError(HTTPStatus.UNPROCESSABLE_ENTITY, error.errors()[0]["msg"]) from error
    return TripOut.of(run_plan(trip))


@router.get("/vehicles", response=list[VehicleOut], summary="Busca no catálogo de veículos")
def vehicles(request: HttpRequest, q: str = "") -> list[VehicleOut]:
    return [VehicleOut.of(vehicle) for vehicle in catalog.search(q)]


@router.get("/places", response={200: list[PlaceOut], 503: ErrorOut}, summary="Busca de endereços no Brasil")
def places(request: HttpRequest, q: str) -> list[PlaceOut]:
    try:
        found = geocoder().search(q)
    except GeocoderUnavailableError as error:
        raise HttpError(HTTPStatus.SERVICE_UNAVAILABLE, str(error)) from error
    return [PlaceOut(name=place.name, lat=place.coordinate.lat, lon=place.coordinate.lon) for place in found]
