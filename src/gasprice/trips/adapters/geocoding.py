import json
import threading
import time
from collections.abc import Callable
from typing import cast

import httpx
from django.core.cache import cache

from gasprice.shared.http import FetchError, get_bytes
from gasprice.trips.application import GeocoderUnavailableError, Place
from gasprice.trips.domain import Coordinate

CACHE_SECONDS = 7 * 24 * 3600
MIN_INTERVAL = 1.0
"""Nominatim's public usage policy: at most one request per second, results cached, no autocomplete."""


class NominatimGeocoder:
    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last = -MIN_INTERVAL

    def search(self, query: str) -> list[Place]:
        text = " ".join(query.split())
        if not text:
            return []
        key = f"nominatim:{text.lower()}"
        cached = cast("list[dict[str, object]] | None", cache.get(key))
        if cached is None:
            cached = [place.model_dump() for place in self._fetch(text)]
            cache.set(key, cached, CACHE_SECONDS)
        return [Place.model_validate(item) for item in cached]

    def _fetch(self, text: str) -> list[Place]:
        with self._lock:
            wait = self._last + MIN_INTERVAL - self._clock()
            if wait > 0:
                self._sleep(wait)
            self._last = self._clock()
            try:
                body = get_bytes(
                    self._client,
                    f"{self._base_url}/search",
                    params={"q": text, "format": "jsonv2", "countrycodes": "br", "limit": "6"},
                    attempts=1,
                )
            except FetchError as error:
                raise GeocoderUnavailableError(str(error)) from error
        return parse_nominatim(body)


def parse_nominatim(body: bytes) -> list[Place]:
    try:
        items = cast("list[dict[str, str]]", json.loads(body))
    except ValueError as error:
        msg = "resposta do geocodificador não é JSON"
        raise GeocoderUnavailableError(msg) from error
    return [
        Place(
            name=item["display_name"], coordinate=Coordinate(lat=float(item["lat"]), lon=float(item["lon"]))
        )
        for item in items
    ]
