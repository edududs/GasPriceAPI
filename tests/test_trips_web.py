import json
from decimal import Decimal

import pytest
from django.test import Client
from fakes import report
from pytest_django.fixtures import Settings
from trip_fakes import FixedRouter, flex

from gasprice.prices.adapters.repository import DjangoPriceRepository
from gasprice.prices.domain import Fuel, State
from gasprice.trips.adapters import composition
from gasprice.trips.adapters.catalog import DjangoVehicleCatalog
from gasprice.trips.application import GeocoderUnavailableError, Place, RouteUnavailableError
from gasprice.trips.domain import Coordinate, VehicleSource

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}
POINTS = "-15.790000,-47.880000;-16.680000,-49.250000"


@pytest.fixture(autouse=True)
def offline(settings: Settings) -> None:
    settings.GASPRICE_ROUTER = "straight"
    settings.GASPRICE_TILE_URL = ""


@pytest.fixture
def vehicle_id() -> str:
    DjangoPriceRepository().save_all(
        [
            report(state=State.DF, average="6.000"),
            report(state=State.GO, average="6.200"),
            report(state=State.DF, fuel=Fuel.ETHANOL, average="3.900"),
        ]
    )
    catalog = DjangoVehicleCatalog()
    catalog.replace(VehicleSource.PBEV, [flex()])
    return catalog.search("argo")[0].id


def test_page_renders_with_empty_catalog(client: Client) -> None:
    page = client.get("/trip/").content.decode()
    assert 'id="trip-map"' in page
    assert 'value="manual" class="sr-only" checked' in page
    assert "Roteamento offline" in page


@pytest.mark.usefixtures("vehicle_id")
def test_vehicle_search_fragment(client: Client) -> None:
    fragment = client.get("/trip/vehicles/", {"vehicle_q": "argo"}, headers=HTMX).content.decode()
    assert "Fiat Argo Drive 1.0 (2025)" in fragment
    assert "data-vehicle-id" in fragment
    assert "Nada encontrado" in client.get("/trip/vehicles/", {"vehicle_q": "fusca"}).content.decode()


def test_vehicle_search_on_an_empty_catalog(client: Client) -> None:
    assert "catálogo está vazio" in client.get("/trip/vehicles/").content.decode()


def test_place_search(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    class Found:
        def search(self, query: str) -> list[Place]:
            return [Place(name=f"{query}, Goiás", coordinate=Coordinate(lat=-16.68, lon=-49.25))]

    monkeypatch.setattr(composition, "geocoder", Found)
    monkeypatch.setattr("gasprice.trips.adapters.views.geocoder", Found)
    monkeypatch.setattr("gasprice.trips.adapters.api.geocoder", Found)
    assert (
        'data-place-lat="-16.680000"' in client.get("/trip/places/", {"place_q": "Goiânia"}).content.decode()
    )
    assert client.get("/trip/places/", {"place_q": " "}).content.decode().strip() == ""
    assert client.get("/api/v1/places", {"q": "Goiânia"}).json()[0]["lat"] == -16.68


def test_place_search_unavailable(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    class Down:
        def search(self, query: str) -> list[Place]:
            raise GeocoderUnavailableError(query)

    monkeypatch.setattr("gasprice.trips.adapters.views.geocoder", Down)
    monkeypatch.setattr("gasprice.trips.adapters.api.geocoder", Down)
    assert "indisponível" in client.get("/trip/places/", {"place_q": "x"}).content.decode()
    assert client.get("/api/v1/places", {"q": "x"}).status_code == 503


def test_estimate_with_a_catalog_vehicle(client: Client, vehicle_id: str) -> None:
    fragment = client.post(
        "/trip/estimate/",
        {
            "points": POINTS,
            "mode": "catalog",
            "vehicle_id": vehicle_id,
            "profile": "highway",
            "round_trip": "on",
        },
        headers=HTMX,
    ).content.decode()
    assert 'id="route-data"' in fragment
    assert "ida e volta" in fragment
    assert "mais barato" in fragment
    assert "você economiza" in fragment
    assert "linha reta" in fragment


def test_estimate_with_manual_consumption_and_missing_prices(client: Client, vehicle_id: str) -> None:
    fragment = client.post(
        "/trip/estimate/",
        {"points": POINTS, "mode": "manual", "kml_gasoline": "12,5", "kml_diesel_s10": "10"},
    ).content.decode()
    assert "12,50 km/L" in fragment
    assert "Sem preços coletados para: diesel s10" in fragment
    assert vehicle_id


@pytest.mark.parametrize(
    ("form", "message"),
    [
        ({"points": "-15.79,-47.88", "mode": "manual", "kml_gasoline": "12"}, "pelo menos dois pontos"),
        ({"points": "x;y", "mode": "manual"}, "pontos marcados é inválido"),
        ({"points": POINTS, "mode": "manual"}, "pelo menos um combustível"),
        ({"points": POINTS, "mode": "manual", "kml_gasoline": "doze"}, "inválido"),
        ({"points": POINTS, "mode": "manual", "kml_gasoline": "500"}, "Dados inválidos"),
        ({"points": POINTS, "mode": "catalog"}, "Escolha um veículo"),
        ({"points": POINTS, "mode": "catalog", "vehicle_id": "999"}, "veículo não encontrado"),
    ],
)
def test_estimate_form_errors(client: Client, form: dict[str, str], message: str) -> None:
    response = client.post("/trip/estimate/", form)
    assert response.status_code == 200
    assert message in response.content.decode()


def test_estimate_when_the_router_is_down(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(composition, "router", lambda: FixedRouter(fail=RouteUnavailableError("503")))
    fragment = client.post("/trip/estimate/", {"points": POINTS, "mode": "manual", "kml_gasoline": "12"})
    assert "não respondeu" in fragment.content.decode()
    response = client.post(
        "/api/v1/trips/estimate",
        json.dumps(
            {
                "points": [{"lat": -15.79, "lon": -47.88}, {"lat": -16.68, "lon": -49.25}],
                "manual": {"gasoline": 12},
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 503


def test_api_estimate(client: Client, vehicle_id: str) -> None:
    body = {
        "points": [{"lat": -15.79, "lon": -47.88}, {"lat": -16.68, "lon": -49.25}],
        "vehicle_id": vehicle_id,
        "profile": "city",
    }
    response = client.post("/api/v1/trips/estimate", json.dumps(body), content_type="application/json")
    data = response.json()
    assert response.status_code == 200
    assert data["approximate"] is True
    assert data["vehicle"]["name"] == "Fiat Argo Drive 1.0 (2025)"
    assert {option["fuel"] for option in data["options"]} == {"gasoline", "ethanol"}
    assert sum(Decimal(part["km"]) for part in data["km_by_state"]) == Decimal(data["distance_km"])
    assert len(data["geometry"]) > 2
    assert client.get("/api/v1/vehicles", {"q": "argo"}).json()[0]["efficiencies"]


def test_api_estimate_errors(client: Client) -> None:
    def post(body: object) -> int:
        return client.post(
            "/api/v1/trips/estimate", json.dumps(body), content_type="application/json"
        ).status_code

    two = [{"lat": -15.79, "lon": -47.88}, {"lat": -16.68, "lon": -49.25}]
    assert post({"points": two}) == 422
    assert post({"points": two, "vehicle_id": "999"}) == 422
    assert post({"points": two[:1], "manual": {"gasoline": 12}}) == 422
