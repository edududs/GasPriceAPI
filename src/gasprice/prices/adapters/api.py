"""Public, read-only JSON API under /api/v1. The schemas are the contract, stated apart from the domain."""

from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Self

from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI, Schema, Status
from ninja.errors import HttpError

from gasprice.prices.adapters.composition import get_board, get_health, get_history, get_latest
from gasprice.prices.domain import (
    CollectionRun,
    DomainError,
    Fuel,
    PriceReport,
    Source,
    State,
    UnknownStateError,
)
from gasprice.trips.adapters.api import router as trips_router


class PriceOut(Schema):
    state: State
    state_name: str
    fuel: Fuel
    source: Source
    period_start: date
    period_end: date
    average: Decimal
    minimum: Decimal | None
    maximum: Decimal | None
    stations: int | None
    unit: str

    @classmethod
    def of(cls, report: PriceReport) -> Self:
        return cls(
            state=report.state,
            state_name=report.state.label,
            fuel=report.fuel,
            source=report.source,
            period_start=report.period_start,
            period_end=report.period_end,
            average=report.average,
            minimum=report.minimum,
            maximum=report.maximum,
            stations=report.stations,
            unit=report.fuel.unit,
        )


class BoardOut(Schema):
    fuel: Fuel
    unit: str
    mean: Decimal | None
    latest_period: date | None
    prices: list[PriceOut]


class StateOut(Schema):
    code: State
    name: str
    region: str


class FuelOut(Schema):
    code: Fuel
    name: str
    unit: str


class RunOut(Schema):
    source: Source
    finished_at: datetime
    written: int
    error: str | None

    @classmethod
    def of(cls, run: CollectionRun | None) -> Self | None:
        if run is None:
            return None
        return cls(source=run.source, finished_at=run.finished_at, written=run.written, error=run.error)


class HealthOut(Schema):
    healthy: bool
    max_age_days: int
    last_success: RunOut | None
    last_run: RunOut | None


class ErrorOut(Schema):
    detail: str


api = NinjaAPI(
    title="GasPrice API",
    version="1.0.0",
    description="Preço médio de revenda dos combustíveis por estado, do levantamento semanal da ANP.",
    urls_namespace="api",
)


api.add_router("/", trips_router)


@api.exception_handler(DomainError)
def domain_error(request: HttpRequest, error: DomainError) -> HttpResponse:
    return api.create_response(request, {"detail": str(error)}, status=HTTPStatus.NOT_FOUND)


@api.get("/states", response=list[StateOut], tags=["catalog"], summary="Estados")
def states(request: HttpRequest) -> list[StateOut]:
    return [StateOut(code=state, name=state.label, region=state.region.value) for state in State]


@api.get("/fuels", response=list[FuelOut], tags=["catalog"], summary="Combustíveis")
def fuels(request: HttpRequest) -> list[FuelOut]:
    return [FuelOut(code=fuel, name=fuel.label, unit=fuel.unit) for fuel in Fuel]


@api.get(
    "/prices",
    response={200: list[PriceOut], 422: ErrorOut},
    tags=["prices"],
    summary="Preço atual por estado e combustível",
)
def prices(request: HttpRequest, fuel: Fuel | None = None, state: str | None = None) -> list[PriceOut]:
    """O levantamento mais recente de cada estado e combustível, filtrável pelos dois."""
    try:
        chosen_state = State.parse(state) if state else None
    except UnknownStateError as error:
        raise HttpError(HTTPStatus.UNPROCESSABLE_ENTITY, str(error)) from error
    return [PriceOut.of(report) for report in get_latest(fuel=fuel, state=chosen_state)]


@api.get("/boards/{fuel}", response=BoardOut, tags=["prices"], summary="Ranking de um combustível")
def board(request: HttpRequest, fuel: Fuel) -> BoardOut:
    """Todos os estados para um combustível, do mais barato ao mais caro, com a média entre estados."""
    result = get_board(fuel)
    return BoardOut(
        fuel=fuel,
        unit=fuel.unit,
        mean=result.mean,
        latest_period=result.latest_period,
        prices=[PriceOut.of(entry) for entry in result.entries],
    )


@api.get(
    "/prices/{state}/{fuel}/history",
    response={200: list[PriceOut], 404: ErrorOut},
    tags=["prices"],
    summary="Histórico de um estado e combustível",
)
def history(request: HttpRequest, state: str, fuel: Fuel, since: date | None = None) -> list[PriceOut]:
    """Série semanal, mais antiga primeiro, de uma única fonte (a melhor disponível)."""
    return [PriceOut.of(report) for report in get_history(State.parse(state), fuel, since=since)]


@api.get("/health", response={200: HealthOut, 503: HealthOut}, tags=["ops"], summary="Saúde da coleta")
def health(request: HttpRequest) -> Status[HealthOut]:
    """503 quando a última coleta bem-sucedida é mais velha que o limite configurado."""
    result = get_health()()
    body = HealthOut(
        healthy=result.healthy,
        max_age_days=result.max_age_days,
        last_success=RunOut.of(result.last_success),
        last_run=RunOut.of(result.last_run),
    )
    return Status(HTTPStatus.OK if result.healthy else HTTPStatus.SERVICE_UNAVAILABLE, body)
