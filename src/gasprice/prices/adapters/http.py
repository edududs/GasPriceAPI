import logging
import time
from collections.abc import Callable
from http import HTTPStatus

import httpx

from gasprice.prices.application import SourceUnavailableError

logger = logging.getLogger(__name__)

USER_AGENT = "gasprice/0.1 (+https://github.com/edududs/GasPriceAPI)"
RETRIABLE = frozenset({HTTPStatus.TOO_MANY_REQUESTS, *(status for status in HTTPStatus if status >= 500)})  # noqa: PLR2004


def build_client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def get_bytes(
    client: httpx.Client,
    url: str,
    *,
    attempts: int = 3,
    backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """GET with retries on network errors, 429 and 5xx. Any other status fails at once.

    Raises SourceUnavailableError with the last reason when every attempt failed.
    """
    reason = ""
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url)
        except httpx.HTTPError as error:
            reason = f"{type(error).__name__}: {error}"
        else:
            if response.is_success:
                return response.content
            reason = f"HTTP {response.status_code}"
            if response.status_code not in RETRIABLE:
                break
        if attempt < attempts:
            delay = backoff * 2 ** (attempt - 1)
            logger.warning("GET %s falhou (%s); nova tentativa em %.0fs", url, reason, delay)
            sleep(delay)
    msg = f"GET {url} falhou: {reason}"
    raise SourceUnavailableError(msg)
