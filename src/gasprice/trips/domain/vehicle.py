from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, Field

from gasprice.prices.domain import Fuel
from gasprice.prices.domain.model import FrozenModel


def _hundredths(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


type KmPerLiter = Annotated[Decimal, Field(gt=0, lt=100), AfterValidator(_hundredths)]

CITY_SHARE = Decimal("0.55")
"""INMETRO's combined figure weighs 55% city and 45% highway driving."""


class DrivingProfile(StrEnum):
    HIGHWAY = "highway"
    MIXED = "mixed"
    CITY = "city"

    @property
    def label(self) -> str:
        return {"highway": "Estrada", "mixed": "Misto", "city": "Cidade"}[self.value]


class Efficiency(FrozenModel):
    """km/L in city and on highway, as the INMETRO label states them."""

    city: KmPerLiter
    highway: KmPerLiter

    def at(self, profile: DrivingProfile) -> Decimal:
        match profile:
            case DrivingProfile.CITY:
                value = self.city
            case DrivingProfile.HIGHWAY:
                value = self.highway
            case DrivingProfile.MIXED:
                # Fuel adds up per km, not km per litre: the combined figure is a harmonic mean.
                value = 1 / (CITY_SHARE / self.city + (1 - CITY_SHARE) / self.highway)
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class VehicleSource(StrEnum):
    PBEV = "pbev"
    REFERENCE = "reference"

    @property
    def label(self) -> str:
        return {
            "pbev": "INMETRO — Programa Brasileiro de Etiquetagem Veicular",
            "reference": "Perfil de referência (aproximado)",
        }[self.value]


class Vehicle(FrozenModel):
    id: str
    source: VehicleSource
    brand: str
    model: str
    version: str = ""
    year: int | None = None
    efficiencies: dict[Fuel, Efficiency]

    @property
    def name(self) -> str:
        parts = [self.brand, self.model, self.version]
        name = " ".join(part for part in parts if part)
        return f"{name} ({self.year})" if self.year else name

    @property
    def is_flex(self) -> bool:
        return {Fuel.GASOLINE, Fuel.ETHANOL} <= self.efficiencies.keys()
