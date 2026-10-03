from enum import StrEnum
from typing import Self

from gasprice.prices.domain.errors import UnknownStateError
from gasprice.prices.domain.text import normalize


class Region(StrEnum):
    NORTH = "Norte"
    NORTHEAST = "Nordeste"
    MIDWEST = "Centro-Oeste"
    SOUTHEAST = "Sudeste"
    SOUTH = "Sul"


class State(StrEnum):
    """The 27 federative units, by their two-letter code."""

    AC = "AC"
    AL = "AL"
    AM = "AM"
    AP = "AP"
    BA = "BA"
    CE = "CE"
    DF = "DF"
    ES = "ES"
    GO = "GO"
    MA = "MA"
    MG = "MG"
    MS = "MS"
    MT = "MT"
    PA = "PA"
    PB = "PB"
    PE = "PE"
    PI = "PI"
    PR = "PR"
    RJ = "RJ"
    RN = "RN"
    RO = "RO"
    RR = "RR"
    RS = "RS"
    SC = "SC"
    SE = "SE"
    SP = "SP"
    TO = "TO"

    @property
    def label(self) -> str:
        return _DETAILS[self][0]

    @property
    def region(self) -> Region:
        return _DETAILS[self][1]

    @classmethod
    def parse(cls, code: str) -> Self:
        """A code as typed in a URL: case and surrounding spaces ignored."""
        try:
            return cls(code.strip().upper())
        except ValueError as error:
            msg = f"UF desconhecida: {code!r}"
            raise UnknownStateError(msg) from error

    @classmethod
    def from_name(cls, name: str) -> Self:
        """A state by its name as a source writes it: `SAO PAULO`, `São Paulo`, or the code itself."""
        key = normalize(name)
        for state in cls:
            if key in {normalize(state.label), state.value}:
                return state
        msg = f"estado desconhecido: {name!r}"
        raise UnknownStateError(msg)


_DETAILS: dict[State, tuple[str, Region]] = {
    State.AC: ("Acre", Region.NORTH),
    State.AL: ("Alagoas", Region.NORTHEAST),
    State.AM: ("Amazonas", Region.NORTH),
    State.AP: ("Amapá", Region.NORTH),
    State.BA: ("Bahia", Region.NORTHEAST),
    State.CE: ("Ceará", Region.NORTHEAST),
    State.DF: ("Distrito Federal", Region.MIDWEST),
    State.ES: ("Espírito Santo", Region.SOUTHEAST),
    State.GO: ("Goiás", Region.MIDWEST),
    State.MA: ("Maranhão", Region.NORTHEAST),
    State.MG: ("Minas Gerais", Region.SOUTHEAST),
    State.MS: ("Mato Grosso do Sul", Region.MIDWEST),
    State.MT: ("Mato Grosso", Region.MIDWEST),
    State.PA: ("Pará", Region.NORTH),
    State.PB: ("Paraíba", Region.NORTHEAST),
    State.PE: ("Pernambuco", Region.NORTHEAST),
    State.PI: ("Piauí", Region.NORTHEAST),
    State.PR: ("Paraná", Region.SOUTH),
    State.RJ: ("Rio de Janeiro", Region.SOUTHEAST),
    State.RN: ("Rio Grande do Norte", Region.NORTHEAST),
    State.RO: ("Rondônia", Region.NORTH),
    State.RR: ("Roraima", Region.NORTH),
    State.RS: ("Rio Grande do Sul", Region.SOUTH),
    State.SC: ("Santa Catarina", Region.SOUTH),
    State.SE: ("Sergipe", Region.NORTHEAST),
    State.SP: ("São Paulo", Region.SOUTHEAST),
    State.TO: ("Tocantins", Region.NORTH),
}
