from collections.abc import Collection, Sequence
from datetime import date

from django.db import transaction
from django.db.models import OuterRef, Subquery

from gasprice.prices.adapters.models import CollectionRunRecord, PriceRecord
from gasprice.prices.domain import CollectionRun, Fuel, PriceReport, Source, State

UPDATED_FIELDS = ["period_start", "average", "minimum", "maximum", "stations", "updated_at"]


class DjangoPriceRepository:
    def save_all(self, reports: Sequence[PriceReport]) -> int:
        records = [
            PriceRecord(
                source=report.source.value,
                state=report.state.value,
                fuel=report.fuel.value,
                period_start=report.period_start,
                period_end=report.period_end,
                average=report.average,
                minimum=report.minimum,
                maximum=report.maximum,
                stations=report.stations,
            )
            for report in reports
        ]
        with transaction.atomic():
            PriceRecord.objects.bulk_create(
                records,
                batch_size=500,
                update_conflicts=True,
                unique_fields=["source", "state", "fuel", "period_end"],
                update_fields=UPDATED_FIELDS,
            )
        return len(records)

    def latest(self, *, fuel: Fuel | None = None, state: State | None = None) -> list[PriceReport]:
        scope = PriceRecord.objects.all()
        if fuel is not None:
            scope = scope.filter(fuel=fuel.value)
        if state is not None:
            scope = scope.filter(state=state.value)
        newest = (
            PriceRecord.objects.filter(
                source=OuterRef("source"), state=OuterRef("state"), fuel=OuterRef("fuel")
            )
            .order_by("-period_end")
            .values("period_end")[:1]
        )
        return [_to_report(record) for record in scope.filter(period_end=Subquery(newest))]

    def history(self, state: State, fuel: Fuel, *, since: date | None = None) -> list[PriceReport]:
        scope = PriceRecord.objects.filter(state=state.value, fuel=fuel.value)
        if since is not None:
            scope = scope.filter(period_end__gte=since)
        return [_to_report(record) for record in scope.order_by("period_end")]

    def record_run(self, run: CollectionRun) -> None:
        CollectionRunRecord.objects.create(
            source=run.source.value,
            started_at=run.started_at,
            finished_at=run.finished_at,
            written=run.written,
            skipped=run.skipped,
            error=run.error,
        )

    def last_run(
        self, *, succeeded: bool | None = None, sources: Collection[Source] | None = None
    ) -> CollectionRun | None:
        scope = CollectionRunRecord.objects.all()
        if sources is not None:
            scope = scope.filter(source__in=[source.value for source in sources])
        if succeeded is not None:
            scope = scope.filter(error__isnull=succeeded)
        record = scope.order_by("-finished_at", "-id").first()
        if record is None:
            return None
        return CollectionRun(
            source=Source(record.source),
            started_at=record.started_at,
            finished_at=record.finished_at,
            written=record.written,
            skipped=record.skipped,
            error=record.error,
        )


def _to_report(record: PriceRecord) -> PriceReport:
    return PriceReport(
        source=Source(record.source),
        state=State(record.state),
        fuel=Fuel(record.fuel),
        period_start=record.period_start,
        period_end=record.period_end,
        average=record.average,
        minimum=record.minimum,
        maximum=record.maximum,
        stations=record.stations,
    )
