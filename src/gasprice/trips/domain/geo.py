import math
from collections.abc import Callable, Sequence
from decimal import Decimal
from itertools import pairwise
from typing import Annotated

from pydantic import Field

from gasprice.prices.domain import State
from gasprice.prices.domain.model import FrozenModel

EARTH_RADIUS_KM = 6371.0088

type StateLocator = Callable[["Coordinate"], State | None]


class Coordinate(FrozenModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]


def distance_km(a: Coordinate, b: Coordinate) -> float:
    """Great-circle distance (haversine)."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat, dlon = lat2 - lat1, math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def midpoint(a: Coordinate, b: Coordinate) -> Coordinate:
    """Plain average: segments of a route line are short enough for it."""
    return Coordinate(lat=(a.lat + b.lat) / 2, lon=(a.lon + b.lon) / 2)


def apportion(
    geometry: Sequence[Coordinate], total_km: Decimal, locate: StateLocator
) -> dict[State | None, Decimal]:
    """Split a route's road distance among the states its line crosses.

    Each segment of the line is assigned to the state of its midpoint, and the shares of line length
    are applied to the road distance: the line is simplified, so its length is shorter than the road
    but its proportions are right. `None` collects what fell outside every state (coastline cuts).
    """
    lengths: dict[State | None, float] = {}
    for a, b in pairwise(geometry):
        state = locate(midpoint(a, b))
        lengths[state] = lengths.get(state, 0.0) + distance_km(a, b)
    line_km = sum(lengths.values())
    if line_km == 0:
        state = locate(geometry[0]) if geometry else None
        return {state: total_km}
    shares = {
        state: (total_km * Decimal(km / line_km)).quantize(Decimal("0.1")) for state, km in lengths.items()
    }
    # Rounding must not create or lose kilometres: the largest share absorbs the difference.
    largest = max(shares, key=lambda state: shares[state])
    shares[largest] += total_km.quantize(Decimal("0.1")) - sum(shares.values())
    return {state: km for state, km in shares.items() if km > 0}
