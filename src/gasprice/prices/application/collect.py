import logging

from gasprice.prices.application.ports import Clock, PriceRepository, PriceSource, SourceUnavailableError
from gasprice.prices.domain import CollectionRun

logger = logging.getLogger(__name__)

SKIPPED_SAMPLE = 10
"""How many skipped lines a run logs individually before summarising the rest."""


class CollectPrices:
    """Read a source and store what it had. Every attempt leaves a run behind, failed or not."""

    def __init__(self, repository: PriceRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def __call__(self, source: PriceSource) -> CollectionRun:
        started_at = self._clock.now()
        try:
            harvest = source.fetch()
        except SourceUnavailableError as error:
            return self._finish(
                CollectionRun(
                    source=source.source,
                    started_at=started_at,
                    finished_at=self._clock.now(),
                    error=str(error),
                )
            )

        for reason in harvest.skipped[:SKIPPED_SAMPLE]:
            logger.warning("%s: ignorado: %s", source.source, reason)
        if len(harvest.skipped) > SKIPPED_SAMPLE:
            logger.warning(
                "%s: mais %d linhas ignoradas", source.source, len(harvest.skipped) - SKIPPED_SAMPLE
            )

        if not harvest.reports:
            # A source that answers but yields nothing usually changed its layout: that is a failure,
            # not a quiet week, and it must not look like a success on the health check.
            error = f"nenhum preço reconhecido ({len(harvest.skipped)} linhas ignoradas)"
            return self._finish(
                CollectionRun(
                    source=source.source,
                    started_at=started_at,
                    finished_at=self._clock.now(),
                    skipped=len(harvest.skipped),
                    error=error,
                )
            )

        written = self._repository.save_all(harvest.reports)
        return self._finish(
            CollectionRun(
                source=source.source,
                started_at=started_at,
                finished_at=self._clock.now(),
                written=written,
                skipped=len(harvest.skipped),
            )
        )

    def _finish(self, run: CollectionRun) -> CollectionRun:
        self._repository.record_run(run)
        if run.succeeded:
            logger.info("%s: %d preços gravados, %d ignorados", run.source, run.written, run.skipped)
        else:
            logger.error("%s: coleta falhou: %s", run.source, run.error)
        return run
