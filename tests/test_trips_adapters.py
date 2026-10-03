import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from django.core.cache import cache
from fakes import report
from pytest_django.fixtures import Settings
from trip_fakes import BRASILIA, GOIANIA

from gasprice.prices.adapters.repository import DjangoPriceRepository
from gasprice.prices.domain import Fuel, State
from gasprice.trips.adapters import composition
from gasprice.trips.adapters.geocoding import NominatimGeocoder, parse_nominatim
from gasprice.trips.adapters.prices import BoardFuelPrices
from gasprice.trips.adapters.routing import OsrmRouter, StraightLineRouter, parse_osrm
from gasprice.trips.adapters.states import GeoJsonStateLocator
from gasprice.trips.application import GeocoderUnavailableError, NoRouteError, RouteUnavailableError
from gasprice.trips.domain import Coordinate

GEOJSON = (
    Path(__file__).resolve().parents[1] / "src" / "gasprice" / "web" / "static" / "geo" / "br-states.json"
)

# Recorded shape of an OSRM /route response (trimmed): distance in metres, duration in seconds.
OSRM_OK = {
    "code": "Ok",
    "routes": [
        {
            "distance": 209312.4,
            "duration": 9301.2,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-47.882, -15.794], [-48.9, -16.3], [-49.254, -16.686]],
            },
        }
    ],
}


def test_parse_osrm() -> None:
    route = parse_osrm(json.dumps(OSRM_OK).encode())
    assert route.distance_km == Decimal("209.3")
    assert route.duration_min == 155
    assert route.geometry[0] == Coordinate(lat=-15.794, lon=-47.882)
    assert not route.approximate


@pytest.mark.parametrize("body", [{"code": "NoRoute", "routes": []}, {"code": "Ok", "routes": []}])
def test_parse_osrm_without_route(body: object) -> None:
    with pytest.raises(NoRouteError):
        parse_osrm(json.dumps(body).encode())


def test_parse_osrm_garbage() -> None:
    with pytest.raises(RouteUnavailableError):
        parse_osrm(b"<html>")


def test_osrm_router_builds_the_request() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=OSRM_OK)

    router = OsrmRouter(httpx.Client(transport=httpx.MockTransport(handle)), base_url="https://osrm.test/")
    router.route([BRASILIA, GOIANIA])
    assert seen[0].url.path == "/route/v1/driving/-47.880000,-15.790000;-49.250000,-16.680000"
    assert seen[0].url.params["overview"] == "simplified"


@pytest.mark.parametrize(("status", "error"), [(400, NoRouteError), (503, RouteUnavailableError)])
def test_osrm_router_errors(status: int, error: type[Exception]) -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status)))
    router = OsrmRouter(client, base_url="https://osrm.test")
    with pytest.raises(error):
        router.route([BRASILIA, GOIANIA])


def test_straight_line_router_is_marked_approximate() -> None:
    route = StraightLineRouter(detour=1.0, speed_kmh=60, steps=4).route([BRASILIA, GOIANIA, BRASILIA])
    assert route.approximate
    assert Decimal(340) < route.distance_km < Decimal(360)
    assert len(route.geometry) == 9
    assert route.duration_min == round(float(route.distance_km))


NOMINATIM = [{"display_name": "Goiânia, Goiás, Brasil", "lat": "-16.68", "lon": "-49.25"}]


def test_parse_nominatim() -> None:
    (place,) = parse_nominatim(json.dumps(NOMINATIM).encode())
    assert place.name.startswith("Goiânia")
    assert place.coordinate == GOIANIA
    with pytest.raises(GeocoderUnavailableError):
        parse_nominatim(b"oops")


def test_nominatim_caches_and_throttles() -> None:
    cache.clear()
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=NOMINATIM)

    now = [100.0]
    slept: list[float] = []
    geocoder = NominatimGeocoder(
        httpx.Client(transport=httpx.MockTransport(handle)),
        base_url="https://nominatim.test",
        clock=lambda: now[0],
        sleep=slept.append,
    )
    assert geocoder.search("  goiânia ") == geocoder.search("Goiânia")
    assert len(seen) == 1, "the second search is served from the cache"
    assert seen[0].url.params["countrycodes"] == "br"
    now[0] += 0.25
    geocoder.search("Anápolis")
    assert slept == [0.75], "one request per second"
    assert geocoder.search("   ") == []


def test_nominatim_unavailable() -> None:
    cache.clear()
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    with pytest.raises(GeocoderUnavailableError):
        NominatimGeocoder(client, base_url="https://nominatim.test", sleep=lambda _: None).search("x")


@pytest.mark.parametrize(
    ("lat", "lon", "state"),
    [
        (-15.79, -47.88, State.DF),  # inside Goiás' outline too: the smaller shape wins
        (-16.68, -49.25, State.GO),
        (-23.55, -46.63, State.SP),
        (-3.10, -60.02, State.AM),
        (-30.03, -51.23, State.RS),
        (-20.0, -30.0, None),
    ],
)
def test_state_locator(lat: float, lon: float, state: State | None) -> None:
    assert GeoJsonStateLocator(GEOJSON).locate(Coordinate(lat=lat, lon=lon)) is state


def test_state_locator_handles_holes(tmp_path: Path) -> None:
    square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"uf": "GO"}, "geometry": {"type": "Polygon", "coordinates": [square, hole]}},
            {
                "properties": {"uf": "AC"},
                "geometry": {"type": "MultiPolygon", "coordinates": [[[[20, 0], [21, 0], [21, 1], [20, 0]]]]},
            },
        ],
    }
    path = tmp_path / "shapes.json"
    path.write_text(json.dumps(geojson))
    locator = GeoJsonStateLocator(path)
    assert locator.locate(Coordinate(lat=1, lon=1)) is State.GO
    assert locator.locate(Coordinate(lat=5, lon=5)) is None
    assert locator.locate(Coordinate(lat=0.2, lon=20.8)) is State.AC


@pytest.mark.django_db
def test_board_prices_feed_the_trip_context() -> None:
    DjangoPriceRepository().save_all(
        [report(state=State.SP, average="6.000"), report(state=State.RJ, average="7.000")]
    )
    table = BoardFuelPrices().table(Fuel.GASOLINE)
    assert table.prices == {State.SP: Decimal("6.000"), State.RJ: Decimal("7.000")}
    assert table.mean == Decimal("6.500")
    assert BoardFuelPrices().table(Fuel.CNG).mean is None


def test_composition_picks_the_configured_router(settings: Settings) -> None:
    settings.GASPRICE_ROUTER = "osrm"
    assert isinstance(composition.router(), OsrmRouter)
    settings.GASPRICE_ROUTER = "straight"
    assert isinstance(composition.router(), StraightLineRouter)
    assert composition.geocoder() is composition.geocoder(), "one throttle per process"
