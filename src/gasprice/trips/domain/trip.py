from decimal import Decimal
from typing import Annotated, Self

from pydantic import Field, model_validator

from gasprice.prices.domain import Fuel, State
from gasprice.prices.domain.model import FrozenModel
from gasprice.trips.domain.estimate import FuelOption
from gasprice.trips.domain.geo import Coordinate
from gasprice.trips.domain.route import Route
from gasprice.trips.domain.vehicle import DrivingProfile, KmPerLiter, Vehicle

MAX_POINTS = 10


class TripRequest(FrozenModel):
    """From A to B, through optional stops, with a catalog vehicle or hand-typed km/L per fuel."""

    points: Annotated[tuple[Coordinate, ...], Field(min_length=2, max_length=MAX_POINTS)]
    profile: DrivingProfile = DrivingProfile.MIXED
    round_trip: bool = False
    vehicle_id: str | None = None
    manual: dict[Fuel, KmPerLiter] = Field(default_factory=dict[Fuel, KmPerLiter])

    @model_validator(mode="after")
    def _one_consumption(self) -> Self:
        if (self.vehicle_id is None) == (not self.manual):
            msg = "escolha um veículo do catálogo ou informe o km/L, não os dois"
            raise ValueError(msg)
        return self


class TripPlan(FrozenModel):
    route: Route
    km_by_state: dict[State | None, Decimal]
    profile: DrivingProfile
    round_trip: bool
    vehicle: Vehicle | None
    options: tuple[FuelOption, ...]
    """Cheapest first."""
    unpriced: tuple[Fuel, ...] = ()
    """Fuels the vehicle takes but for which no price is known anywhere."""

    @property
    def distance_km(self) -> Decimal:
        return sum(self.km_by_state.values(), Decimal(0))

    @property
    def duration_min(self) -> int:
        return self.route.duration_min * (2 if self.round_trip else 1)

    @property
    def cheapest(self) -> FuelOption | None:
        return self.options[0] if self.options else None

    @property
    def savings(self) -> Decimal | None:
        """How much the cheapest option saves over the next one, when there is a choice."""
        if len(self.options) < 2:  # noqa: PLR2004
            return None
        return self.options[1].cost - self.options[0].cost
