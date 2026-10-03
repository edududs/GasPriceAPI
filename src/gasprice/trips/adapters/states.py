"""Which state a point is in, from the same GeoJSON the map draws. Plain ray casting, no GIS stack."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from gasprice.prices.domain import State
from gasprice.trips.domain import Coordinate

type Ring = Sequence[tuple[float, float]]


@dataclass(frozen=True)
class _Shape:
    state: State
    polygons: tuple[tuple[Ring, ...], ...]
    """Each polygon is its outer ring followed by its holes; (lon, lat) pairs as GeoJSON writes them."""
    box: tuple[float, float, float, float]
    area: float

    def contains(self, lon: float, lat: float) -> bool:
        west, south, east, north = self.box
        if not (west <= lon <= east and south <= lat <= north):
            return False
        return any(
            _inside(rings[0], lon, lat) and not any(_inside(hole, lon, lat) for hole in rings[1:])
            for rings in self.polygons
        )


class GeoJsonStateLocator:
    """Smaller shapes are tested first: the simplified Goiás covers the Distrito Federal without a hole."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._shapes: list[_Shape] | None = None

    def locate(self, point: Coordinate) -> State | None:
        for shape in self._load():
            if shape.contains(point.lon, point.lat):
                return shape.state
        return None

    def _load(self) -> list[_Shape]:
        if self._shapes is None:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            features = cast("list[dict[str, dict[str, object]]]", data["features"])
            self._shapes = sorted((_shape(feature) for feature in features), key=lambda shape: shape.area)
        return self._shapes


def _shape(feature: dict[str, dict[str, object]]) -> _Shape:
    geometry = feature["geometry"]
    raw = cast("list[object]", geometry["coordinates"])
    nested = [raw] if geometry["type"] == "Polygon" else raw
    polygons = tuple(
        tuple(
            tuple((float(x), float(y)) for x, y in cast("list[list[float]]", ring))
            for ring in cast("list[object]", polygon)
        )
        for polygon in nested
    )
    xs = [x for polygon in polygons for x, _ in polygon[0]]
    ys = [y for polygon in polygons for _, y in polygon[0]]
    return _Shape(
        state=State(cast("str", feature["properties"]["uf"])),
        polygons=polygons,
        box=(min(xs), min(ys), max(xs), max(ys)),
        area=sum(abs(_area(polygon[0])) for polygon in polygons),
    )


def _inside(ring: Ring, x: float, y: float) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, [*ring[1:], ring[0]], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _area(ring: Ring) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, [*ring[1:], ring[0]], strict=True)) / 2
