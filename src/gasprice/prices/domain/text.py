"""Text as the sources write it: accents, mixed case, Brazilian decimal commas."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from gasprice.prices.domain.errors import InvalidPriceError

_SPACES = re.compile(r"\s+")
_NOT_NUMERIC = re.compile(r"[^\d,.\-]")


def normalize(text: str) -> str:
    """Uppercase, no accents, hyphens as spaces, single spaces. `Óleo  Diesel S-10` -> `OLEO DIESEL S 10`."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _SPACES.sub(" ", stripped.replace("-", " ")).strip().upper()


def parse_decimal(text: str) -> Decimal:
    """Read a price as a person writes it: `R$ 6,19`, `6.199`, `1.234,56`, `6,199`.

    With both separators, the last one is the decimal mark. With only a comma, it is the decimal
    mark. With only dots, a single dot is the decimal mark (sources never write thousands here).
    """
    cleaned = _NOT_NUMERIC.sub("", text)
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as error:
        msg = f"não é um preço: {text!r}"
        raise InvalidPriceError(msg) from error
    if not value.is_finite():
        msg = f"não é um preço: {text!r}"
        raise InvalidPriceError(msg)
    return value
