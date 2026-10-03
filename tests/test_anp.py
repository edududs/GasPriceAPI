from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from workbooks import row, workbook

from gasprice.prices.adapters.anp import AnpSource, find_latest_workbook, parse_workbook
from gasprice.prices.application import SourceUnavailableError
from gasprice.prices.domain import Fuel, Source, State

PAGE_URL = "https://www.gov.br/anp/levantamento"


def test_parses_the_states_sheet_and_skips_the_municipalities_one() -> None:
    harvest = parse_workbook(
        workbook(
            [
                row("SAO PAULO", "GASOLINA COMUM", 6.199, minimum=5.79, maximum=6.99),
                row("DISTRITO FEDERAL", "ETANOL HIDRATADO", "4,559", minimum="-", maximum=" "),
                row("RIO GRANDE DO SUL", "GLP", 112.5, minimum=95, maximum=130),
            ]
        )
    )
    assert harvest.skipped == ()
    first, second, third = harvest.reports
    assert first.source is Source.ANP
    assert (first.state, first.fuel) == (State.SP, Fuel.GASOLINE)
    assert (first.period_start, first.period_end) == (date(2026, 9, 20), date(2026, 9, 26))
    assert (first.average, first.minimum, first.maximum) == (
        Decimal("6.199"),
        Decimal("5.790"),
        Decimal("6.990"),
    )
    assert first.stations == 312
    assert (second.state, second.fuel, second.average) == (State.DF, Fuel.ETHANOL, Decimal("4.559"))
    assert (second.minimum, second.maximum) == (None, None)
    assert (third.fuel, third.average) == (Fuel.LPG, Decimal("112.500"))


def test_finds_the_header_wherever_it_is() -> None:
    data = workbook([row("BAHIA", "OLEO DIESEL S10", 6.1)], title_rows=0, with_municipalities=False)
    assert parse_workbook(data).reports[0].fuel is Fuel.DIESEL_S10


def test_bad_rows_become_reasons_not_failures() -> None:
    harvest = parse_workbook(
        workbook(
            [
                row("SAO PAULO", "QUEROSENE", 6.0),
                row("ATLANTIDA", "GNV", 5.0),
                row("PARANA", "GNV", "-"),
                row("PARANA", "GASOLINA COMUM", average=True),
                row("PARANA", "GASOLINA COMUM", 6.0, minimum=7.0),
                row("PARANA", "ETANOL", 4.2),
            ]
        )
    )
    assert [item.state for item in harvest.reports] == [State.PR]
    assert len(harvest.skipped) == 5
    assert harvest.skipped[0].startswith("linha 11: produto desconhecido")


def test_text_dates_and_stations_are_read() -> None:
    data = workbook([("20/09/2026", "2026-09-26", "NORTE", "ACRE", "GNV", "1.024", "R$/m3", "5,10")])
    report = parse_workbook(data).reports[0]
    assert (report.period_start, report.period_end, report.stations) == (
        date(2026, 9, 20),
        date(2026, 9, 26),
        1024,
    )


def test_invalid_date_is_skipped() -> None:
    harvest = parse_workbook(workbook([("ontem", "hoje", "NORTE", "ACRE", "GNV", 1, "R$/m3", 5.1)]))
    assert harvest.reports == ()
    assert "data inválida" in harvest.skipped[0]


def test_a_file_that_is_not_a_workbook_is_unavailable() -> None:
    with pytest.raises(SourceUnavailableError, match="planilha"):
        parse_workbook(b"<html>manuten\xc3\xa7\xc3\xa3o</html>")


def test_a_workbook_without_the_table_is_unavailable() -> None:
    from io import BytesIO  # noqa: PLC0415

    from openpyxl import Workbook  # noqa: PLC0415

    buffer = BytesIO()
    Workbook().save(buffer)
    with pytest.raises(SourceUnavailableError, match="nenhuma aba"):
        parse_workbook(buffer.getvalue())


def test_find_latest_workbook_picks_the_newest_weekly_file() -> None:
    page = """
      <a href="/anp/arquivos/resumo_semanal_lpc_2026-09-06_2026-09-12.xlsx">anterior</a>
      <a href='https://www.gov.br/anp/arquivos/resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx'>atual</a>
      <a href="/anp/arquivos/mensal-estados.xlsx">mensal</a>
    """
    assert find_latest_workbook(page, PAGE_URL) == (
        "https://www.gov.br/anp/arquivos/resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx"
    )
    assert find_latest_workbook('<a href="dados.xlsx">x</a>', PAGE_URL) == "https://www.gov.br/anp/dados.xlsx"
    with pytest.raises(SourceUnavailableError):
        find_latest_workbook("<p>nada</p>", PAGE_URL)


def _client(routes: dict[str, bytes]) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        body = routes.get(str(request.url))
        return httpx.Response(200, content=body) if body is not None else httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_source_discovers_and_downloads_the_weekly_workbook() -> None:
    link = "https://www.gov.br/anp/resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx"
    client = _client(
        {PAGE_URL: f'<a href="{link}">x</a>'.encode(), link: workbook([row("SAO PAULO", "GNV", 5.0)])}
    )
    harvest = AnpSource(client, page_url=PAGE_URL).fetch()
    assert harvest.reports[0].fuel is Fuel.CNG


def test_source_reads_an_explicit_url_or_file(tmp_path: Path) -> None:
    data = workbook([row("SAO PAULO", "GNV", 5.0)])
    url = "https://example.org/semanal-estados-desde-2013.xlsx"
    assert AnpSource(_client({url: data}), page_url=PAGE_URL, workbook=url).fetch().reports

    path = tmp_path / "semanal.xlsx"
    path.write_bytes(data)
    assert AnpSource(_client({}), page_url=PAGE_URL, workbook=str(path)).fetch().reports
    with pytest.raises(SourceUnavailableError, match="não foi possível ler"):
        AnpSource(_client({}), page_url=PAGE_URL, workbook=str(tmp_path / "missing.xlsx")).fetch()
