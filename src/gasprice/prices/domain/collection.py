from datetime import datetime

from gasprice.prices.domain.model import FrozenModel
from gasprice.prices.domain.source import Source


class CollectionRun(FrozenModel):
    """One attempt to bring a source's prices in. `error` set means nothing was written."""

    source: Source
    started_at: datetime
    finished_at: datetime
    written: int = 0
    skipped: int = 0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None
