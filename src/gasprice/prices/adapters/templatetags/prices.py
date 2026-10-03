from decimal import Decimal

from django import template
from django.utils.formats import number_format

from gasprice.prices.domain import Fuel

register = template.Library()


@register.filter
def brl(value: Decimal | None, fuel: Fuel | None = None) -> str:
    """`R$ 6,299` per liter; LPG is priced per cylinder, so two places like any other money."""
    if value is None:
        return "—"
    places = 2 if fuel == Fuel.LPG else 3
    return f"R$ {number_format(value, places, use_l10n=True, force_grouping=True)}"


@register.filter
def signed(value: Decimal) -> str:
    text = number_format(abs(value), 1, use_l10n=True)
    return f"+{text}%" if value > 0 else (f"−{text}%" if value < 0 else "0%")
