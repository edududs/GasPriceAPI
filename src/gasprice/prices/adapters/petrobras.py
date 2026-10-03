"""Petrobras' public price composition page: one HTML page per state, the final price in one element.

It only covers gasoline and has no survey period, so the period is the day of the read. It ranks below
the ANP and is kept as a fallback and for continuity with the first version of this project.
"""

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError

from gasprice.prices.adapters.http import get_bytes
from gasprice.prices.application import Harvest, SourceUnavailableError
from gasprice.prices.domain import DomainError, Fuel, PriceReport, Source, State, parse_decimal

BASE_URL = "https://precos.petrobras.com.br/web/precos-dos-combustiveis/w/gasolina/"
PRICE_SELECTOR = "#telafinal-precofinal"


class PetrobrasSource:
    source = Source.PETROBRAS

    def __init__(
        self,
        client: httpx.Client,
        *,
        today: Callable[[], date],
        states: Iterable[State] = State,
        base_url: str = BASE_URL,
    ) -> None:
        self._client = client
        self._today = today
        self._states = tuple(states)
        self._base_url = base_url

    def fetch(self) -> Harvest:
        """One state failing never stops the others; it becomes a skipped line."""
        reports: list[PriceReport] = []
        skipped: list[str] = []
        today = self._today()
        for state in self._states:
            try:
                page = get_bytes(self._client, f"{self._base_url}{state.value.lower()}", attempts=2)
                reports.append(
                    PriceReport(
                        source=Source.PETROBRAS,
                        state=state,
                        fuel=Fuel.GASOLINE,
                        period_start=today,
                        period_end=today,
                        average=parse_price(page),
                    )
                )
            except (SourceUnavailableError, DomainError, ValidationError) as error:
                skipped.append(f"{state}: {error}")
        return Harvest(reports=tuple(reports), skipped=tuple(skipped))


def parse_price(page: bytes) -> Decimal:
    element = BeautifulSoup(page, "html.parser").select_one(PRICE_SELECTOR)
    if element is None:
        msg = f"preço não encontrado na página ({PRICE_SELECTOR})"
        raise DomainError(msg)
    return parse_decimal(element.get_text())
