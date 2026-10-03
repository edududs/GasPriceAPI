from collections.abc import Iterator

import pytest
from fakes import FixedClock, MemoryPriceRepository

from gasprice.prices.adapters.repository import DjangoPriceRepository
from gasprice.prices.application import PriceRepository


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture(params=["memory", "django"])
def repository(request: pytest.FixtureRequest) -> Iterator[PriceRepository]:
    """Both adapters, so the in-memory fake used elsewhere is proven to behave like the real one."""
    if request.param == "memory":
        yield MemoryPriceRepository()
    else:
        request.getfixturevalue("db")
        yield DjangoPriceRepository()
