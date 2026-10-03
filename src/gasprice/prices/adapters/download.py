import httpx

from gasprice.prices.application import SourceUnavailableError
from gasprice.shared.http import FetchError, get_bytes


def download(client: httpx.Client, url: str, *, attempts: int = 3) -> bytes:
    """`get_bytes`, with failure stated in this context's terms: the price source is unavailable."""
    try:
        return get_bytes(client, url, attempts=attempts)
    except FetchError as error:
        raise SourceUnavailableError(str(error)) from error
