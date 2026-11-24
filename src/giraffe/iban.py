"""IBAN normalization, validation (mod-97) and detection in free text."""
import re

# Fixed lengths for common SEPA countries; others are only length-range checked.
_LENGTHS = {
    "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22,
    "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27,
    "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21, "LT": 20,
    "LU": 20, "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28,
    "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
}

_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?:[ \t ]?[A-Z0-9]){11,34}")


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def is_valid(value: str) -> bool:
    iban = normalize(value)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    expected = _LENGTHS.get(iban[:2])
    if expected is not None and len(iban) != expected:
        return False
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return int(digits) % 97 == 1


def format_iban(value: str) -> str:
    iban = normalize(value)
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def find_ibans(text: str) -> list[str]:
    """Return valid, normalized IBANs found in text, in order of appearance.

    Uppercase only, so ordinary words don't match. A greedy match may swallow
    trailing words ("... 00 BIC"), so it is trimmed to the longest valid prefix.
    """
    found: list[str] = []
    for m in _CANDIDATE.finditer(text):
        compact = normalize(m.group(0))
        for length in range(min(len(compact), 34), 14, -1):
            if is_valid(compact[:length]):
                if compact[:length] not in found:
                    found.append(compact[:length])
                break
    return found
