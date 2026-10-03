from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command
from django.test import Client
from django.utils import timezone
from fakes import SATURDAY, report
from workbooks import row, workbook

from gasprice.prices.adapters.repository import DjangoPriceRepository
from gasprice.prices.domain import CollectionRun, Fuel, Source, State

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


@pytest.fixture
def stored() -> DjangoPriceRepository:
    repository = DjangoPriceRepository()
    repository.save_all(
        [
            *(report(end=SATURDAY - timedelta(weeks=n), average=f"6.{n}00") for n in range(5)),
            report(state=State.AC, average="7.400"),
            report(state=State.SP, fuel=Fuel.LPG, average="110.50"),
        ]
    )
    now = timezone.now()
    repository.record_run(CollectionRun(source=Source.ANP, started_at=now, finished_at=now, written=7))
    return repository


@pytest.mark.usefixtures("stored")
def test_home_page_renders_map_board_and_footer(client: Client) -> None:
    page = client.get("/").content.decode()
    assert 'id="map"' in page
    assert 'id="map-data"' in page
    assert "São Paulo" in page
    assert "R$ 6,000" in page
    assert "Última coleta em" in page
    assert "Dados de demonstração" not in page


@pytest.mark.usefixtures("stored")
def test_home_page_preselects_a_state(client: Client) -> None:
    page = client.get("/", {"fuel": "gasoline", "state": "sp"}).content.decode()
    assert 'data-selected="SP"' in page
    assert "<svg" in page
    assert "R$ 110,50" in page


def test_unknown_fuel_or_state_is_404(client: Client) -> None:
    assert client.get("/", {"fuel": "querosene"}).status_code == 404
    assert client.get("/", {"state": "XX"}).status_code == 404
    assert client.get("/states/XX/", headers=HTMX).status_code == 404


def test_empty_database_explains_how_to_collect(client: Client) -> None:
    page = client.get("/").content.decode()
    assert "collect_prices" in page
    assert "Nenhuma coleta registrada" in page


@pytest.mark.usefixtures("stored")
def test_board_fragment_swaps_tabs_out_of_band(client: Client) -> None:
    fragment = client.get("/board/lpg/", headers=HTMX).content.decode()
    assert "<html" not in fragment
    assert 'hx-swap-oob="true"' in fragment
    assert "R$ 110,50" in fragment


def test_fragments_redirect_without_htmx(client: Client) -> None:
    assert client.get("/board/ethanol/")["Location"] == "/?fuel=ethanol"
    assert client.get("/states/sp/", {"fuel": "lpg"})["Location"] == "/?fuel=lpg&state=SP"


@pytest.mark.usefixtures("stored")
def test_state_fragment(client: Client) -> None:
    fragment = client.get("/states/ac/", {"fuel": "ethanol"}, headers=HTMX).content.decode()
    assert "Acre" in fragment
    assert "Sem preços de etanol" in fragment


def test_demo_banner(client: Client) -> None:
    DjangoPriceRepository().save_all([report(source=Source.DEMO)])
    assert "Dados de demonstração" in client.get("/").content.decode()


@pytest.mark.usefixtures("stored")
def test_api(client: Client) -> None:
    assert len(client.get("/api/v1/states").json()) == 27
    assert {item["code"] for item in client.get("/api/v1/fuels").json()} == {fuel.value for fuel in Fuel}

    prices = client.get("/api/v1/prices", {"state": "sp"}).json()
    assert [(item["fuel"], item["average"]) for item in prices] == [("gasoline", "6.000"), ("lpg", "110.500")]
    assert client.get("/api/v1/prices", {"state": "zz"}).status_code == 422
    assert client.get("/api/v1/prices", {"fuel": "querosene"}).status_code == 422

    board = client.get("/api/v1/boards/gasoline").json()
    assert [item["state"] for item in board["prices"]] == ["SP", "AC"]
    assert board["mean"] == "6.700"

    history = client.get("/api/v1/prices/SP/gasoline/history", {"since": "2026-09-12"}).json()
    assert [item["average"] for item in history] == ["6.200", "6.100", "6.000"]
    assert client.get("/api/v1/prices/XX/gasoline/history").status_code == 404


@pytest.mark.usefixtures("stored")
def test_health(client: Client) -> None:
    body = client.get("/api/v1/health").json()
    assert body["healthy"] is True
    assert body["last_success"]["written"] == 7


def test_health_is_503_without_a_real_collection(client: Client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["last_success"] is None


def test_collect_command_from_a_local_workbook(tmp_path: Path) -> None:
    path = tmp_path / "semanal.xlsx"
    path.write_bytes(workbook([row("SAO PAULO", "GASOLINA COMUM", 6.2), row("PARANA", "GNV", 5.1)]))
    out = StringIO()
    call_command("collect_prices", "--workbook", str(path), stdout=out)
    assert "2 preços gravados" in out.getvalue()
    assert len(DjangoPriceRepository().latest()) == 2


def test_collect_command_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(CommandError, match="não foi possível ler"):
        call_command("collect_prices", "--workbook", str(tmp_path / "missing.xlsx"), stdout=StringIO())
    assert DjangoPriceRepository().last_run(succeeded=False) is not None


def test_demo_seed_fills_every_state_and_fuel() -> None:
    call_command("collect_prices", "--source", "demo", stdout=StringIO())
    latest = DjangoPriceRepository().latest()
    assert {(item.state, item.fuel) for item in latest} == {(s, f) for s in State for f in Fuel}
