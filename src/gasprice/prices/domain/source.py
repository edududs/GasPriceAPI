from enum import StrEnum


class Source(StrEnum):
    """Where a price came from. When two sources cover the same state and fuel, the lower rank wins."""

    ANP = "anp"
    PETROBRAS = "petrobras"
    DEMO = "demo"

    @property
    def label(self) -> str:
        return _DETAILS[self][0]

    @property
    def rank(self) -> int:
        return _DETAILS[self][1]


_DETAILS: dict[Source, tuple[str, int]] = {
    Source.ANP: ("ANP — Levantamento de Preços de Combustíveis", 0),
    Source.PETROBRAS: ("Petrobras — composição de preços", 1),
    Source.DEMO: ("Dados de demonstração", 9),
}
