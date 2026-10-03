from decimal import Decimal
from typing import ClassVar

from django.db import models

from gasprice.trips.domain import VehicleSource

SOURCES = [(source.value, source.label) for source in VehicleSource]


def efficiency_field() -> "models.DecimalField[Decimal | None]":
    return models.DecimalField(max_digits=5, decimal_places=2, null=True)


class VehicleRecord(models.Model):
    source = models.CharField(max_length=16, choices=SOURCES)
    brand = models.CharField(max_length=60)
    model = models.CharField(max_length=120)
    version = models.CharField(max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(null=True)
    search_key = models.CharField(max_length=400, db_index=True)
    """Brand, model, version and year normalized (no accents, uppercase): what search matches against."""
    gasoline_city = efficiency_field()
    gasoline_highway = efficiency_field()
    ethanol_city = efficiency_field()
    ethanol_highway = efficiency_field()
    diesel_city = efficiency_field()
    diesel_highway = efficiency_field()

    class Meta:
        ordering: ClassVar = ["brand", "model", "version", "-year"]

    def __str__(self) -> str:
        return f"{self.brand} {self.model} {self.version} {self.year or ''}".strip()
