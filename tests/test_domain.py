from datetime import date
from decimal import Decimal

import pytest
from fakes import SATURDAY, report
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from gasprice.prices.domain import (
    Board,
    Fuel,
    InvalidPriceError,
    PriceReport,
    Region,
    Source,
    State,
    UnknownFuelError,
    UnknownStateError,
    normalize,
    parse_decimal,
    preferred,
    series,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("R$ 6,19", "6.19"),
        ("6,199", "6.199"),
        ("6.199", "6.199"),
        ("1.234,56", "1234.56"),
        ("1,234.56", "1234.56"),
        (" 108,50 ", "108.50"),
    ],
)
def test_parse_decimal_reads_the_ways_prices_are_written(text: str, expected: str) -> None:
    assert parse_decimal(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "-", "abc", "R$"])
def test_parse_decimal_rejects_what_is_not_a_number(text: str) -> None:
    with pytest.raises(InvalidPriceError):
        parse_decimal(text)


@given(st.decimals(min_value=Decimal("0.001"), max_value=Decimal(9999), places=3))
def test_parse_decimal_round_trips_brazilian_formatting(value: Decimal) -> None:
    written = f"R$ {value:,.3f}".replace(",", "_").replace(".", ",").replace("_", ".")
    assert parse_decimal(written) == value


def test_normalize_strips_accents_case_hyphens_and_spaces() -> None:
    assert normalize("  Óleo   Diesel S-10 ") == "OLEO DIESEL S 10"


@pytest.mark.parametrize("name", ["SAO PAULO", "São Paulo", "são  paulo", "SP"])
def test_state_from_name_accepts_source_spellings(name: str) -> None:
    assert State.from_name(name) is State.SP


def test_state_details_cover_every_state() -> None:
    assert len(State) == 27
    assert {state.region for state in State} == set(Region)
    assert State.DF.label == "Distrito Federal"


def test_state_parse_and_unknowns() -> None:
    assert State.parse(" df ") is State.DF
    with pytest.raises(UnknownStateError):
        State.parse("XX")
    with pytest.raises(UnknownStateError):
        State.from_name("Atlântida")


@pytest.mark.parametrize(
    ("product", "fuel"),
    [
        ("GASOLINA COMUM", Fuel.GASOLINE),
        ("GASOLINA ADITIVADA", Fuel.GASOLINE_PREMIUM),
        ("ETANOL HIDRATADO", Fuel.ETHANOL),
        ("ÓLEO DIESEL", Fuel.DIESEL),
        ("OLEO DIESEL S10", Fuel.DIESEL_S10),
        ("Óleo Diesel S-10", Fuel.DIESEL_S10),
        ("GNV", Fuel.CNG),
        ("GLP", Fuel.LPG),
    ],
)
def test_fuel_from_product_name(product: str, fuel: Fuel) -> None:
    assert Fuel.from_product_name(product) is fuel


def test_fuel_parse_and_unknowns() -> None:
    assert Fuel.parse("Ethanol") is Fuel.ETHANOL
    assert all(fuel.label and fuel.unit for fuel in Fuel)
    with pytest.raises(UnknownFuelError):
        Fuel.parse("querosene")
    with pytest.raises(UnknownFuelError):
        Fuel.from_product_name("QUEROSENE")


def test_report_keeps_three_places() -> None:
    assert report(average="6.19949").average == Decimal("6.199")


@pytest.mark.parametrize(
    "changes",
    [
        {"average": Decimal(0)},
        {"minimum": Decimal("7.0")},
        {"maximum": Decimal("5.0")},
        {"period_start": date(2026, 10, 1)},
        {"stations": -1},
    ],
)
def test_report_rejects_inconsistent_values(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PriceReport.model_validate({**dict(report()), **changes})


def test_preferred_picks_best_source_then_newest_period() -> None:
    old_anp = report(end=date(2026, 9, 19))
    new_anp = report(end=SATURDAY)
    newer_petrobras = report(source=Source.PETROBRAS, end=date(2026, 9, 28))
    demo = report(source=Source.DEMO, state=State.RJ)
    chosen = preferred([newer_petrobras, old_anp, new_anp, demo])
    assert chosen[State.SP, Fuel.GASOLINE] == new_anp
    assert chosen[State.RJ, Fuel.GASOLINE] == demo


def test_series_keeps_one_source_oldest_first() -> None:
    first, second = report(end=date(2026, 9, 19)), report(end=SATURDAY)
    other = report(source=Source.PETROBRAS, end=date(2026, 9, 22))
    assert series([second, other, first]) == [first, second]
    assert series([]) == []


def test_board_ranks_states_and_summarises() -> None:
    reports = [
        report(state=State.SP, average="6.000"),
        report(state=State.AC, average="7.500"),
        report(state=State.PR, average="6.300", end=date(2026, 9, 19)),
        report(state=State.RJ, fuel=Fuel.ETHANOL, average="4.000"),
    ]
    board = Board.of(Fuel.GASOLINE, reports)
    assert [entry.state for entry in board.entries] == [State.SP, State.PR, State.AC]
    assert board.cheapest is not None
    assert board.cheapest.state is State.SP
    assert board.priciest is not None
    assert board.priciest.state is State.AC
    assert board.mean == Decimal("6.600")
    assert board.latest_period == SATURDAY
    assert board.sources == {Source.ANP}


def test_empty_board() -> None:
    board = Board.of(Fuel.CNG, [])
    assert board.is_empty
    assert board.cheapest is None
    assert board.priciest is None
    assert board.mean is None
    assert board.latest_period is None
