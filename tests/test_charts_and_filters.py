from datetime import timedelta
from decimal import Decimal

from fakes import SATURDAY, report

from gasprice.prices.adapters.charts import sparkline
from gasprice.prices.adapters.templatetags.prices import brl, signed
from gasprice.prices.domain import Fuel


def test_sparkline_needs_two_points() -> None:
    assert sparkline([]) is None
    assert sparkline([report()]) is None


def test_sparkline_geometry() -> None:
    reports = [
        report(end=SATURDAY - timedelta(weeks=2), average="6.000"),
        report(end=SATURDAY - timedelta(weeks=1), average="5.000"),
        report(end=SATURDAY, average="7.000"),
    ]
    chart = sparkline(reports, width=100, height=50, pad=0)
    assert chart is not None
    assert chart.line == "M0.0,25.0 L50.0,50.0 L100.0,0.0"
    assert chart.area.endswith("L100.0,50 L0.0,50 Z")
    assert chart.lowest.report.average == Decimal("5.000")
    assert chart.highest.report.average == Decimal("7.000")
    assert chart.first == reports[0]
    assert chart.last == reports[-1]
    assert chart.change == Decimal("16.7")


def test_flat_sparkline_does_not_divide_by_zero() -> None:
    chart = sparkline([report(end=SATURDAY - timedelta(weeks=1)), report()], width=10, height=10, pad=0)
    assert chart is not None
    assert chart.change == Decimal("0.0")


def test_brl_and_signed() -> None:
    assert brl(Decimal("6.199")) == "R$ 6,199"
    assert brl(Decimal("1234.5"), Fuel.LPG) == "R$ 1.234,50"
    assert brl(None) == "—"
    assert signed(Decimal("3.9")) == "+3,9%"
    assert signed(Decimal("-1.25")) == "−1,2%"
    assert signed(Decimal(0)) == "0%"
