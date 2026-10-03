"""The trip planner page and its htmx fragments. Errors render inside the fragment with status 200:
htmx does not swap 4xx bodies by default, and the message belongs where the result would be."""

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from gasprice.prices.domain import DomainError, Fuel, parse_decimal
from gasprice.trips.adapters.composition import catalog, geocoder, plan_trip
from gasprice.trips.application import GeocoderUnavailableError, NoRouteError, RouteUnavailableError
from gasprice.trips.domain import MAX_POINTS, Coordinate, DrivingProfile, TripError, TripRequest

MANUAL_FUELS = (Fuel.GASOLINE, Fuel.ETHANOL, Fuel.DIESEL_S10)


@require_GET
def trip_page(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "trip.html",
        {
            "profiles": list(DrivingProfile),
            "manual_fuels": MANUAL_FUELS,
            "max_points": MAX_POINTS,
            "tile_url": settings.GASPRICE_TILE_URL,
            "tile_attribution": settings.GASPRICE_TILE_ATTRIBUTION,
            "approximate_router": settings.GASPRICE_ROUTER == "straight",
            "catalog_empty": not catalog.search("", limit=1),
        },
    )


@require_GET
def vehicle_search(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("vehicle_q", "")
    return render(
        request, "partials/vehicles.html", {"vehicles": catalog.search(query, limit=12), "query": query}
    )


@require_GET
def place_search(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("place_q", "").strip()
    context: dict[str, Any] = {"query": query, "places": []}
    if query:
        try:
            context["places"] = geocoder().search(query)
        except GeocoderUnavailableError:
            context["error"] = (
                "A busca de endereços está indisponível agora. Marque o ponto clicando no mapa."
            )
    return render(request, "partials/places.html", context)


@require_POST
def trip_estimate(request: HttpRequest) -> HttpResponse:
    try:
        trip = _trip_request(request)
        plan = plan_trip()(trip)
    except _FormError as error:
        return _error(request, str(error))
    except (TripError, NoRouteError) as error:
        return _error(request, f"Não foi possível traçar a rota: {error}.")
    except RouteUnavailableError:
        return _error(request, "O serviço de rotas não respondeu. Tente de novo em instantes.")
    route_data = {"geometry": [(point.lat, point.lon) for point in plan.route.geometry]}
    return render(request, "partials/trip_result.html", {"plan": plan, "route_data": route_data})


class _FormError(Exception):
    pass


def _error(request: HttpRequest, message: str) -> HttpResponse:
    return render(request, "partials/trip_result.html", {"error": message})


def _trip_request(request: HttpRequest) -> TripRequest:
    points = _points(request.POST.get("points", ""))
    if len(points) < 2:  # noqa: PLR2004
        msg = "Marque pelo menos dois pontos no mapa: a origem e o destino."
        raise _FormError(msg)
    vehicle_id: str | None = None
    manual: dict[Fuel, Decimal] = {}
    if request.POST.get("mode") == "manual":
        manual = _manual(request)
        if not manual:
            msg = "Informe o km/L de pelo menos um combustível."
            raise _FormError(msg)
    else:
        vehicle_id = request.POST.get("vehicle_id") or None
        if vehicle_id is None:
            msg = "Escolha um veículo do catálogo ou passe para “Informar km/L”."
            raise _FormError(msg)
    try:
        return TripRequest(
            points=tuple(points),
            profile=DrivingProfile(request.POST.get("profile", DrivingProfile.MIXED.value)),
            round_trip=request.POST.get("round_trip") == "on",
            vehicle_id=vehicle_id,
            manual=manual,
        )
    except (ValidationError, ValueError) as error:
        reason = error.errors()[0]["msg"] if isinstance(error, ValidationError) else str(error)
        msg = f"Dados inválidos: {reason}"
        raise _FormError(msg) from error


def _points(raw: str) -> list[Coordinate]:
    points: list[Coordinate] = []
    for pair in filter(None, raw.split(";")):
        try:
            lat, lon = (float(part) for part in pair.split(","))
            points.append(Coordinate(lat=lat, lon=lon))
        except (ValueError, ValidationError) as error:
            msg = "Um dos pontos marcados é inválido. Remova-o e marque de novo."
            raise _FormError(msg) from error
    return points


def _manual(request: HttpRequest) -> dict[Fuel, Decimal]:
    manual: dict[Fuel, Decimal] = {}
    for fuel in MANUAL_FUELS:
        raw = request.POST.get(f"kml_{fuel.value}", "").strip()
        if not raw:
            continue
        try:
            manual[fuel] = parse_decimal(raw)
        except DomainError as error:
            msg = f"km/L de {fuel.label.lower()} inválido: {raw!r}"
            raise _FormError(msg) from error
    return manual
