import json
from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise
from typing import cast

import httpx

from gasprice.shared.http import FetchError, get_bytes
from gasprice.trips.application import NoRouteError, RouteUnavailableError
from gasprice.trips.domain import Coordinate, Route, distance_km

KM = Decimal("0.1")


class OsrmRouter:
    """OSRM's HTTP API: the public demo server or a self-hosted one, same code, different `base_url`."""

    def __init__(self, client: httpx.Client, *, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    def route(self, points: Sequence[Coordinate]) -> Route:
        path = ";".join(f"{point.lon:.6f},{point.lat:.6f}" for point in points)
        try:
            body = get_bytes(
                self._client,
                f"{self._base_url}/route/v1/driving/{path}",
                params={"overview": "simplified", "geometries": "geojson"},
                attempts=2,
            )
        except FetchError as error:
            if "HTTP 400" in str(error):
                # OSRM answers 400 for points it cannot snap to a road: a fact about the points.
                raise NoRouteError(str(error)) from error
            raise RouteUnavailableError(str(error)) from error
        return parse_osrm(body)


def parse_osrm(body: bytes) -> Route:
    try:
        data = cast("dict[str, object]", json.loads(body))
    except ValueError as error:
        msg = "resposta do roteador não é JSON"
        raise RouteUnavailableError(msg) from error
    routes = cast("list[dict[str, object]]", data.get("routes") or [])
    if data.get("code") != "Ok" or not routes:
        msg = f"sem rota entre os pontos ({data.get('code')})"
        raise NoRouteError(msg)
    best = routes[0]
    geometry = cast("dict[str, list[list[float]]]", best["geometry"])
    return Route(
        distance_km=(Decimal(str(best["distance"])) / 1000).quantize(KM),
        duration_min=round(float(cast("float", best["duration"])) / 60),
        geometry=tuple(Coordinate(lat=lat, lon=lon) for lon, lat in geometry["coordinates"]),
    )


class StraightLineRouter:
    """No road network: great-circle distance times a detour factor, at a constant average speed.

    For development without network access and as an explicit fallback. Every route it returns is
    marked approximate, and the page says so.
    """

    def __init__(self, *, detour: float = 1.25, speed_kmh: float = 75.0, steps: int = 24) -> None:
        self._detour = detour
        self._speed = speed_kmh
        self._steps = steps

    def route(self, points: Sequence[Coordinate]) -> Route:
        line: list[Coordinate] = [points[0]]
        km = 0.0
        for a, b in pairwise(points):
            km += distance_km(a, b) * self._detour
            line.extend(
                Coordinate(
                    lat=a.lat + (b.lat - a.lat) * step / self._steps,
                    lon=a.lon + (b.lon - a.lon) * step / self._steps,
                )
                for step in range(1, self._steps + 1)
            )
        return Route(
            distance_km=Decimal(km).quantize(KM),
            duration_min=round(km / self._speed * 60),
            geometry=tuple(line),
            approximate=True,
        )
