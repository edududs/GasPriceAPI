from enum import StrEnum
from typing import Self

from gasprice.prices.domain.errors import UnknownFuelError
from gasprice.prices.domain.text import normalize


class Fuel(StrEnum):
    GASOLINE = "gasoline"
    GASOLINE_PREMIUM = "gasoline_premium"
    ETHANOL = "ethanol"
    DIESEL = "diesel"
    DIESEL_S10 = "diesel_s10"
    CNG = "cng"
    LPG = "lpg"

    @property
    def label(self) -> str:
        return _DETAILS[self][0]

    @property
    def unit(self) -> str:
        return _DETAILS[self][1]

    @classmethod
    def parse(cls, value: str) -> Self:
        try:
            return cls(value.strip().lower())
        except ValueError as error:
            msg = f"combustível desconhecido: {value!r}"
            raise UnknownFuelError(msg) from error

    @classmethod
    def from_product_name(cls, name: str) -> Self:
        """A fuel by the product name the ANP survey uses, in any of the spellings seen over the years."""
        try:
            return cls(_PRODUCT_NAMES[normalize(name)])
        except KeyError as error:
            msg = f"produto desconhecido: {name!r}"
            raise UnknownFuelError(msg) from error


_DETAILS: dict[Fuel, tuple[str, str]] = {
    Fuel.GASOLINE: ("Gasolina comum", "R$/l"),
    Fuel.GASOLINE_PREMIUM: ("Gasolina aditivada", "R$/l"),
    Fuel.ETHANOL: ("Etanol", "R$/l"),
    Fuel.DIESEL: ("Diesel", "R$/l"),
    Fuel.DIESEL_S10: ("Diesel S10", "R$/l"),
    Fuel.CNG: ("GNV", "R$/m³"),
    Fuel.LPG: ("GLP (botijão 13 kg)", "R$/13 kg"),
}

_PRODUCT_NAMES: dict[str, Fuel] = {
    "GASOLINA": Fuel.GASOLINE,
    "GASOLINA COMUM": Fuel.GASOLINE,
    "GASOLINA ADITIVADA": Fuel.GASOLINE_PREMIUM,
    "ETANOL": Fuel.ETHANOL,
    "ETANOL HIDRATADO": Fuel.ETHANOL,
    "DIESEL": Fuel.DIESEL,
    "OLEO DIESEL": Fuel.DIESEL,
    "DIESEL S10": Fuel.DIESEL_S10,
    "OLEO DIESEL S10": Fuel.DIESEL_S10,
    "OLEO DIESEL S 10": Fuel.DIESEL_S10,
    "GNV": Fuel.CNG,
    "GLP": Fuel.LPG,
}
