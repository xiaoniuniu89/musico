from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template
from django.utils import formats

from apps.tenancy.localization import normalize_currency_code

register = template.Library()


@register.filter
def money_from_cents(value, currency_code: str = "USD"):
    """Render an integer cents value with locale-aware number formatting."""
    normalized_currency = normalize_currency_code(currency_code)
    if value in (None, ""):
        return f"{normalized_currency} 0.00"
    try:
        amount = Decimal(value) / Decimal("100")
    except (InvalidOperation, ValueError, TypeError):
        return f"{normalized_currency} 0.00"
    amount_label = formats.number_format(amount, decimal_pos=2, use_l10n=True, force_grouping=True)
    return f"{normalized_currency} {amount_label}"
