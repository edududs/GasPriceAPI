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


PBEV_GROUPS = ("", "", "", "", "", "QUILOMETRAGEM POR LITRO", None, None, None)
PBEV_FUELS = ("", "", "", "", "", "Etanol", None, "Gasolina ou Diesel", None)
PBEV_HEADER = (
    "Categoria",
    "Marca",
    "Modelo",
    "Versão",
    "Combustível",
    "Cidade",
    "Estrada",
    "Cidade",
    "Estrada",
)


def pbev_workbook(rows: Sequence[Row], *, title_rows: int = 3) -> bytes:
    """Like the INMETRO table: the km/L titles span three header rows, with merged group cells.

    Merged cells read back as the value in their first cell and None in the rest, which is what
    the `None` entries reproduce.
    """
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    for index in range(title_rows):
        sheet.append(["PROGRAMA BRASILEIRO DE ETIQUETAGEM VEICULAR" if index == 0 else None])
    sheet.append([*PBEV_HEADER[:5], *PBEV_GROUPS[5:]])
    sheet.append([None] * 5 + list(PBEV_FUELS[5:]))
    sheet.append([None] * 5 + list(PBEV_HEADER[5:]))
    for item in rows:
        sheet.append(list(item))
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def plain_vehicle_sheet(rows: Sequence[Row]) -> bytes:
    """A hand-made sheet with a one-row header, which the same parser accepts."""
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(
        [
            "MARCA",
            "MODELO",
            "VERSÃO",
            "ANO",
            "GASOLINA CIDADE",
            "GASOLINA ESTRADA",
            "ETANOL CIDADE",
            "ETANOL ESTRADA",
        ]
    )
    for item in rows:
        sheet.append(list(item))
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()
