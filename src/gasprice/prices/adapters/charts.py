"""Server-side sparkline: the history chart is an SVG path computed here, no chart library on the page."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from gasprice.prices.domain import PriceReport


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    report: PriceReport


@dataclass(frozen=True)
class Sparkline:
    width: int
    height: int
    line: str
    area: str
    points: tuple[Point, ...]
    lowest: Point
    highest: Point

    @property
    def first(self) -> PriceReport:
        return self.points[0].report

    @property
    def last(self) -> PriceReport:
        return self.points[-1].report

    @property
    def change(self) -> Decimal:
        """Percent change from the first to the last point, one decimal."""
        start, end = self.first.average, self.last.average
        return ((end - start) / start * 100).quantize(Decimal("0.1"))


def sparkline(
    reports: Sequence[PriceReport], *, width: int = 320, height: int = 96, pad: int = 6
) -> Sparkline | None:
    """None below two points: a single point is not a trend."""
    if len(reports) < 2:  # noqa: PLR2004
        return None
    prices = [float(report.average) for report in reports]
    low, high = min(prices), max(prices)
    spread = (high - low) or 1.0
    step = (width - 2 * pad) / (len(reports) - 1)
    points = tuple(
        Point(
            x=round(pad + index * step, 1),
            y=round(pad + (high - price) / spread * (height - 2 * pad), 1),
            report=report,
        )
        for index, (price, report) in enumerate(zip(prices, reports, strict=True))
    )
    line = "M" + " L".join(f"{point.x},{point.y}" for point in points)
    area = f"{line} L{points[-1].x},{height} L{points[0].x},{height} Z"
    return Sparkline(
        width=width,
        height=height,
        line=line,
        area=area,
        points=points,
        lowest=min(points, key=lambda point: point.report.average),
        highest=max(points, key=lambda point: point.report.average),
    )
