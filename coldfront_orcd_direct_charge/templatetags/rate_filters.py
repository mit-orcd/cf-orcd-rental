# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Template filters for formatting rental rates.

Usage in templates:
    {% load rate_filters %}
    ${{ current_rate.rate|format_rate }}

The format_rate_value() function can also be called directly from
Python code (serializers, admin, management commands).
"""

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def format_rate_value(value):
    """Format a rate with minimum 2 decimal places, stripping trailing zeros.

    Strips trailing zeros from the fractional part but always preserves
    at least 2 decimal places.  This gives clean display for common
    rates while keeping precision when it matters.

    Examples:
        >>> format_rate_value(Decimal("8.000000"))
        '8.00'
        >>> format_rate_value(Decimal("0.010000"))
        '0.01'
        >>> format_rate_value(Decimal("8.123456"))
        '8.123456'
        >>> format_rate_value(Decimal("0.005000"))
        '0.005'
        >>> format_rate_value(Decimal("126.000000"))
        '126.00'
        >>> format_rate_value(None)
        ''
    """
    if value is None:
        return ""

    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)

    # normalize() strips trailing zeros: 8.000000 -> 8, 8.120000 -> 8.12
    normalized = d.normalize()

    # Determine how many decimal places the normalized form has
    sign, digits, exponent = normalized.as_tuple()
    # exponent is negative for fractional digits, 0 or positive for integers
    actual_dp = max(-exponent, 0)

    # Ensure at least 2 decimal places
    dp = max(actual_dp, 2)
    fmt = f"{{:.{dp}f}}"
    return fmt.format(d)


@register.filter
def format_rate(value):
    """Django template filter: format a rate for display.

    Usage: {{ rate_value|format_rate }}
    """
    return format_rate_value(value)
