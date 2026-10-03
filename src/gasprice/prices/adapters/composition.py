"""Wiring: the one place that knows which adapter plays each port."""

from django.conf import settings

from gasprice.prices.adapters.clock import SystemClock
from gasprice.prices.adapters.repository import DjangoPriceRepository
from gasprice.prices.application import GetBoard, GetHealth, GetHistory, GetLatest, GetStateOverview

repository = DjangoPriceRepository()
clock = SystemClock()

get_board = GetBoard(repository)
get_latest = GetLatest(repository)
get_history = GetHistory(repository)
get_state_overview = GetStateOverview(repository, clock)


def get_health() -> GetHealth:
    return GetHealth(repository, clock, max_age_days=settings.GASPRICE_MAX_AGE_DAYS)
