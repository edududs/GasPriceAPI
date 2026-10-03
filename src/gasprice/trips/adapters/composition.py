"""Wiring for the trips context. Functions, not module constants, so settings overrides take effect."""

from functools import cache

import httpx
from django.conf import settings

from gasprice.shared.http import build_client
from gasprice.trips.adapters.catalog import DjangoVehicleCatalog
from gasprice.trips.adapters.geocoding import NominatimGeocoder
from gasprice.trips.adapters.prices import BoardFuelPrices
from gasprice.trips.adapters.routing import OsrmRouter, StraightLineRouter
from gasprice.trips.adapters.states import GeoJsonStateLocator
from gasprice.trips.application import Geocoder, PlanTrip, RouteProvider

catalog = DjangoVehicleCatalog()
locator = GeoJsonStateLocator(settings.PACKAGE_DIR / "web" / "static" / "geo" / "br-states.json")


@cache
def _client() -> httpx.Client:
    """One pooled client per process: a client per request would leak connections."""
    return build_client(settings.GASPRICE_HTTP_TIMEOUT)


def router() -> RouteProvider:
    if settings.GASPRICE_ROUTER == "straight":
        return StraightLineRouter()
    return OsrmRouter(_client(), base_url=settings.GASPRICE_OSRM_URL)


@cache
def _geocoder(base_url: str) -> NominatimGeocoder:
    # One instance per URL for the whole process: the one-request-per-second throttle lives in it.
    return NominatimGeocoder(_client(), base_url=base_url)


def geocoder() -> Geocoder:
    return _geocoder(settings.GASPRICE_NOMINATIM_URL)


def plan_trip() -> PlanTrip:
    return PlanTrip(router(), locator, BoardFuelPrices(), catalog)
