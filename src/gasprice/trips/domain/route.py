from decimal import Decimal
from typing import Annotated

from pydantic import Field

from gasprice.prices.domain.model import FrozenModel
from gasprice.trips.domain.geo import Coordinate


class Route(FrozenModel):
    distance_km: Annotated[Decimal, Field(ge=0)]
    duration_min: Annotated[int, Field(ge=0)]
    geometry: tuple[Coordinate, ...]
    approximate: bool = False
    """True when the distance was estimated without a road network (straight line times a factor)."""
