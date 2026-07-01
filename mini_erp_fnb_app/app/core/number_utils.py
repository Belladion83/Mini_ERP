from decimal import Decimal, InvalidOperation
import re
from typing import Any


def normalize_locale_number(value: Any, default: str | None = None) -> str | None:
    """Normalize ERP/Vietnamese number text to a backend decimal string.

    Supported examples:
    - 1.234.567,89 -> 1234567.89
    - 150.000      -> 150000      (VN thousands)
    - 150000,50    -> 150000.50   (VN decimal)
    - 150000.5000  -> 150000.5000 (backend decimal)

    The function is intentionally tolerant because HTML number fields may be
    transformed to text by JS, and cached browsers may still post locale text.
    """
    if value is None:
        return default
    if isinstance(value, Decimal):
        return str(value)
    s = str(value).strip()
    if s == "":
        return default

    # Remove common display text and whitespace, but keep separators/sign.
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(?i)vnd", "", s)
    s = s.replace("%", "")
    s = re.sub(r"[^0-9,\.\-]", "", s)
    if s in ("", "-", ",", "."):
        return default

    negative = s.startswith("-")
    s = s.replace("-", "")
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")

    if last_comma >= 0 and last_dot >= 0:
        # Whichever separator appears last is treated as the decimal separator.
        if last_comma > last_dot:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif last_comma >= 0:
        parts = s.split(",")
        if len(parts) == 2:
            s = parts[0] + "." + parts[1]
        else:
            s = "".join(parts[:-1]) + "." + parts[-1]
    elif last_dot >= 0:
        parts = s.split(".")
        if len(parts) > 2:
            # VN thousand grouping: 1.234.567
            s = "".join(parts)
        elif len(parts) == 2:
            left, right = parts
            # In VN input, 1.234 usually means one thousand two hundred thirty-four.
            # Backend decimals from SQL Numeric normally keep 4/6 decimals, e.g. 150.0000.
            if len(right) == 3 and 1 <= len(left) <= 3:
                s = left + right
            else:
                s = left + "." + right

    s = re.sub(r"[^0-9\.]", "", s)
    if s in ("", "."):
        return default
    if s.count(".") > 1:
        first, rest = s.split(".", 1)
        s = first + "." + rest.replace(".", "")
    return ("-" if negative else "") + s


def parse_decimal(value: Any, default: str = "0") -> Decimal:
    normalized = normalize_locale_number(value, default)
    if normalized is None or normalized == "":
        normalized = default
    try:
        return Decimal(str(normalized))
    except (InvalidOperation, ValueError):
        return Decimal(str(default))


def parse_decimal_strict(value: Any) -> Decimal:
    normalized = normalize_locale_number(value, None)
    if normalized is None:
        raise InvalidOperation("Invalid number")
    return Decimal(str(normalized))
