"""Generic vehicle profiles for when the INMETRO table has not been imported.

Rounded figures in the range the PBEV labels show for each class; they are not any specific model and
the page says so. Importing the PBEV table gives real models, and typing km/L always overrides both.
"""

from decimal import Decimal

from gasprice.prices.domain import Fuel
from gasprice.trips.application import VehicleHarvest
from gasprice.trips.domain import Efficiency, Vehicle, VehicleSource

BRAND = "Referência"


def _flex(gasoline: tuple[str, str], ethanol: tuple[str, str]) -> dict[Fuel, Efficiency]:
    return {
        Fuel.GASOLINE: Efficiency(city=Decimal(gasoline[0]), highway=Decimal(gasoline[1])),
        Fuel.ETHANOL: Efficiency(city=Decimal(ethanol[0]), highway=Decimal(ethanol[1])),
    }


PROFILES: tuple[tuple[str, dict[Fuel, Efficiency]], ...] = (
    ("Hatch compacto 1.0 flex", _flex(("13.0", "14.5"), ("9.0", "10.2"))),
    ("Hatch ou sedã 1.6 flex", _flex(("11.0", "13.0"), ("7.7", "9.0"))),
    ("SUV compacto turbo flex", _flex(("11.3", "13.4"), ("7.9", "9.4"))),
    ("SUV médio 2.0 flex", _flex(("9.3", "11.0"), ("6.5", "7.7"))),
    ("Picape média diesel", {Fuel.DIESEL_S10: Efficiency(city=Decimal("9.0"), highway=Decimal("11.0"))}),
)


class ReferenceProfiles:
    source = VehicleSource.REFERENCE

    def read(self) -> VehicleHarvest:
        return VehicleHarvest(
            vehicles=tuple(
                Vehicle(id="", source=self.source, brand=BRAND, model=model, efficiencies=efficiencies)
                for model, efficiencies in PROFILES
            )
        )
