"""HTML pages. Full page on a normal request; only the swapped fragment when htmx asks."""

from decimal import Decimal
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django_htmx.middleware import HtmxDetails

from gasprice.prices.adapters.charts import sparkline
from gasprice.prices.adapters.composition import get_board, get_health, get_state_overview
from gasprice.prices.domain import Board, DomainError, Fuel, Source, State

DEFAULT_FUEL = Fuel.GASOLINE


class HtmxRequest(HttpRequest):
    htmx: HtmxDetails


def _fuel(value: str | None) -> Fuel:
    if not value:
        return DEFAULT_FUEL
    try:
        return Fuel.parse(value)
    except DomainError as error:
        raise Http404(str(error)) from error


def _state(value: str) -> State:
    try:
        return State.parse(value)
    except DomainError as error:
        raise Http404(str(error)) from error


def _board_context(fuel: Fuel) -> dict[str, Any]:
    board = get_board(fuel)
    return {
        "board": board,
        "fuel": fuel,
        "fuels": list(Fuel),
        "is_demo": Source.DEMO in board.sources,
        "map_data": _map_data(board),
        "rows": _rows(board),
    }


def _rows(board: Board) -> list[dict[str, Any]]:
    """Each entry with the length of its bar: 15% for the cheapest, 100% for the priciest."""
    if board.cheapest is None or board.priciest is None:
        return []
    low, high = board.cheapest.average, board.priciest.average
    spread = (high - low) or Decimal(1)
    return [
        {"report": entry, "share": round(15 + 85 * (entry.average - low) / spread)} for entry in board.entries
    ]


def _map_data(board: Board) -> dict[str, Any]:
    return {
        "fuel": board.fuel.value,
        "label": board.fuel.label,
        "unit": board.fuel.unit,
        "places": 2 if board.fuel == Fuel.LPG else 3,
        "prices": {entry.state.value: float(entry.average) for entry in board.entries},
        "names": {state.value: state.label for state in State},
    }


@require_GET
def index(request: HtmxRequest) -> HttpResponse:
    fuel = _fuel(request.GET.get("fuel"))
    state = request.GET.get("state")
    selected = _state(state) if state else None
    context = _board_context(fuel) | {"health": get_health()(), "selected_state": selected}
    if selected is not None:
        context |= _state_context(selected, fuel)
    return render(request, "index.html", context)


@require_GET
def board(request: HtmxRequest, fuel: str) -> HttpResponse:
    chosen = _fuel(fuel)
    if not request.htmx:
        return redirect(f"{reverse('index')}?fuel={chosen.value}")
    return render(request, "partials/board.html", _board_context(chosen))


def _state_context(state: State, fuel: Fuel) -> dict[str, Any]:
    overview = get_state_overview(state, fuel)
    return {"overview": overview, "chart": sparkline(overview.history), "fuel": fuel}


@require_GET
def state_detail(request: HtmxRequest, state: str) -> HttpResponse:
    chosen = _state(state)
    fuel = _fuel(request.GET.get("fuel"))
    if not request.htmx:
        return redirect(f"{reverse('index')}?fuel={fuel.value}&state={chosen.value}")
    return render(request, "partials/state.html", _state_context(chosen, fuel))
