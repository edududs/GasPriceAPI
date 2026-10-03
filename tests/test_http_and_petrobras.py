from datetime import date
from decimal import Decimal

import httpx
import pytest

from gasprice.prices.adapters.http import build_client, get_bytes
from gasprice.prices.adapters.petrobras import BASE_URL, PetrobrasSource, parse_price
from gasprice.prices.application import SourceUnavailableError
from gasprice.prices.domain import DomainError, Fuel, Source, State


def _sequence(*responses: httpx.Response | Exception) -> tuple[httpx.Client, list[str]]:
    calls: list[str] = []
    pending = list(responses)

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        item = pending.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.Client(transport=httpx.MockTransport(handle)), calls


def test_get_bytes_retries_server_errors_and_network_failures() -> None:
    client, calls = _sequence(
        httpx.ConnectError("boom"), httpx.Response(503), httpx.Response(200, content=b"ok")
    )
    delays: list[float] = []
    assert get_bytes(client, "https://x.test/", sleep=delays.append) == b"ok"
    assert len(calls) == 3
    assert delays == [2.0, 4.0]


def test_get_bytes_gives_up_at_once_on_a_client_error() -> None:
    client, calls = _sequence(httpx.Response(404))
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        get_bytes(client, "https://x.test/", sleep=lambda _: None)
    assert len(calls) == 1


def test_get_bytes_reports_the_last_reason() -> None:
    client, _ = _sequence(httpx.Response(500), httpx.Response(502))
    with pytest.raises(SourceUnavailableError, match="HTTP 502"):
        get_bytes(client, "https://x.test/", attempts=2, sleep=lambda _: None)


def test_build_client_identifies_itself() -> None:
    with build_client(5) as client:
        assert "gasprice" in client.headers["User-Agent"]


PAGE = b'<div><span class="h4 real-value" id="telafinal-precofinal"> 6,29 </span></div>'


def test_parse_price() -> None:
    assert parse_price(PAGE) == Decimal("6.29")
    with pytest.raises(DomainError):
        parse_price(b"<html></html>")


def test_petrobras_isolates_each_state_failure() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sp"):
            return httpx.Response(200, content=PAGE)
        if request.url.path.endswith("/rj"):
            return httpx.Response(200, content=b"<html>layout novo</html>")
        return httpx.Response(404)

    source = PetrobrasSource(
        httpx.Client(transport=httpx.MockTransport(handle)),
        today=lambda: date(2026, 9, 28),
        states=[State.SP, State.RJ, State.MG],
    )
    harvest = source.fetch()
    assert source.source is Source.PETROBRAS
    assert [(item.state, item.fuel, item.average) for item in harvest.reports] == [
        (State.SP, Fuel.GASOLINE, Decimal("6.290"))
    ]
    assert harvest.reports[0].period_end == date(2026, 9, 28)
    assert len(harvest.skipped) == 2
    assert BASE_URL.endswith("/gasolina/")
