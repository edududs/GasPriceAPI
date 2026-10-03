from typing import ClassVar

from django.db import models

from gasprice.prices.domain import Fuel, Source, State

SOURCES = [(source.value, source.label) for source in Source]
STATES = [(state.value, state.label) for state in State]
FUELS = [(fuel.value, fuel.label) for fuel in Fuel]


class PriceRecord(models.Model):
    source = models.CharField(max_length=16, choices=SOURCES)
    state = models.CharField(max_length=2, choices=STATES)
    fuel = models.CharField(max_length=24, choices=FUELS)
    period_start = models.DateField()
    period_end = models.DateField()
    average = models.DecimalField(max_digits=8, decimal_places=3)
    minimum = models.DecimalField(max_digits=8, decimal_places=3, null=True)
    maximum = models.DecimalField(max_digits=8, decimal_places=3, null=True)
    stations = models.PositiveIntegerField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["source", "state", "fuel", "period_end"], name="one_report_per_period"
            ),
            models.CheckConstraint(condition=models.Q(average__gt=0), name="average_positive"),
            models.CheckConstraint(
                condition=models.Q(period_start__lte=models.F("period_end")), name="period_ordered"
            ),
        ]
        indexes: ClassVar = [
            models.Index(fields=["fuel", "state", "-period_end"], name="fuel_state_period"),
        ]

    def __str__(self) -> str:
        return f"{self.source} {self.state} {self.fuel} {self.period_end}: {self.average}"


class CollectionRunRecord(models.Model):
    source = models.CharField(max_length=16, choices=SOURCES)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(db_index=True)
    written = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    error = models.TextField(null=True)  # noqa: DJ001  NULL is "succeeded"; an empty message is not

    def __str__(self) -> str:
        outcome = self.error or f"{self.written} gravados"
        return f"{self.source} @ {self.finished_at:%Y-%m-%d %H:%M}: {outcome}"
