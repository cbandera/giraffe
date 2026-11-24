"""Parsing of German and international number formats."""
import re
from decimal import Decimal, InvalidOperation


def parse_amount(value: str) -> Decimal | None:
    """Parse '1.234,56', '1,234.56', '12,5', '12.50 €' ... Returns None if unparseable."""
    s = re.sub(r"(?i)eur(o)?|€|\s", "", value or "")
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None
    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        dec = "." if last_dot > last_comma else ","
    elif last_dot >= 0 or last_comma >= 0:
        sep = "." if last_dot >= 0 else ","
        parts = s.split(sep)
        if len(parts) > 2:
            dec = None  # repeated separator: thousands
        elif len(parts[1]) == 3 and parts[0] not in ("0", ""):
            dec = None  # '1.234' / '1,234': thousands (the usual trap)
        else:
            dec = sep
    else:
        dec = None
    if dec is None:
        s = s.replace(".", "").replace(",", "")
    else:
        thousands = "," if dec == "." else "."
        s = s.replace(thousands, "")
        if s.count(dec) != 1:
            return None
        s = s.replace(dec, ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def format_amount(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"
