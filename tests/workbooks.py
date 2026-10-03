"""Workbooks shaped like the ANP's: title rows above a header that is not on the first line."""

from collections.abc import Sequence
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook

HEADER = (
    "DATA INICIAL",
    "DATA FINAL",
    "REGIÃO",
    "ESTADO",
    "PRODUTO",
    "NÚMERO DE POSTOS PESQUISADOS",
    "UNIDADE DE MEDIDA",
    "PREÇO MÉDIO REVENDA",
    "DESVIO PADRÃO REVENDA",
    "PREÇO MÍNIMO REVENDA",
    "PREÇO MÁXIMO REVENDA",
    "COEF DE VARIAÇÃO REVENDA",
)

type Cell = str | int | float | bool | datetime | None
type Row = Sequence[Cell]


def row(state: str, product: str, average: Cell, *, minimum: Cell = None, maximum: Cell = None) -> Row:
    return (
        datetime(2026, 9, 20),
        datetime(2026, 9, 26),
        "SUDESTE",
        state,
        product,
        312,
        "R$/l",
        average,
        0.2,
        minimum,
        maximum,
        0.03,
    )


def workbook(rows: Sequence[Row], *, title_rows: int = 9, with_municipalities: bool = True) -> bytes:
    book = Workbook()
    if with_municipalities:
        # First on purpose: the parser must skip it even though it has ESTADO and PRODUTO.
        municipalities = book.active
        assert municipalities is not None
        municipalities.title = "MUNICIPIOS"
        municipalities.append(
            ("DATA INICIAL", "DATA FINAL", "ESTADO", "MUNICÍPIO", "PRODUTO", "PREÇO MÉDIO REVENDA")
        )
        municipalities.append(
            (datetime(2026, 9, 20), datetime(2026, 9, 26), "SAO PAULO", "CAMPINAS", "GLP", 1.0)
        )
        states = book.create_sheet("ESTADOS")
    else:
        states = book.active
        assert states is not None
    for index in range(title_rows):
        states.append(("AGÊNCIA NACIONAL DO PETRÓLEO" if index == 0 else None,))
    states.append(HEADER)
    for item in rows:
        states.append(list(item))
    states.append(())
    states.append(("Fonte: ANP/SDL",))
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()
