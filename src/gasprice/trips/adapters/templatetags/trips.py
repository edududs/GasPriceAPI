from decimal import Decimal

from django import template
from django.utils.formats import number_format

register = template.Library()


@register.filter
def duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest:02d} min" if rest else f"{hours} h"


@register.filter
def km(value: Decimal) -> str:
    return f"{number_format(value, 0 if value >= 100 else 1, use_l10n=True, force_grouping=True)} km"  # noqa: PLR2004


@register.filter
def number(value: Decimal, places: int = 1) -> str:
    return number_format(value, places, use_l10n=True, force_grouping=True)
