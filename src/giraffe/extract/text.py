"""Regex-based extraction from plain invoice text."""
import re

from .. import iban as iban_mod
from ..amounts import format_amount, parse_amount
from .models import TEXT, PaymentData

# Highest priority first.
AMOUNT_KEYWORDS = [
    r"zu\s+zahlen|zahlbetrag|zahlungsbetrag|amount\s+due|total\s+due|balance\s+due|offener\s+betrag",
    r"rechnungsbetrag|rechnungssumme|invoice\s+total",
    r"gesamtbetrag|endbetrag|endsumme|gesamtsumme|brutto|total|summe",
]
_AMOUNT = re.compile(r"(?<![\d.,])\d+(?:[.,]\d{3})*[.,]\d{2}(?!\d)")
_SKIP_LINE = re.compile(r"netto|net\b|zwischensumme|subtotal|mwst|ust\b|steuer|vat|tax", re.I)
_NUMBER = re.compile(
    r"(?:Rechnungs-?\s*(?:nummer|nr\.?)|Rechnung\s*(?:Nr\.?|Nummer)|Invoice\s*(?:No\.?|Number|Nr\.?|#)|"
    r"Beleg(?:nummer|-?\s*Nr\.?)?)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/_.]*[A-Z0-9])",
    re.I,
)
_BIC = re.compile(r"(?:BIC|SWIFT)(?:[-/ ]?Code)?[^A-Za-z0-9\n]{0,5}([A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b")
_PAYEE_KEY = re.compile(
    r"(?:Kontoinhaber(?:in)?|Zahlungsempf(?:ä|ae)nger|Empf(?:ä|ae)nger|Inhaber|Account\s+holder|Beneficiary)"
    r"[ \t]*[:\-][ \t]*(.+?)(?:[ \t]{2,}|$)", re.I | re.M)
_ANSCHRIFT = re.compile(r"^[ \t]*Anschrift\b[ \t]*(:?)[ \t]*(.*)$", re.I | re.M)
_NOT_NAME = re.compile(r"iban|bic|konto|bank|sparkasse|volksbank|www\.|@|tel|fax|seite|page", re.I)
_NON_EUR = re.compile(r"\b(CHF|USD|GBP|SEK|NOK|DKK|PLN|CZK|HUF)\b|[$£]")


def _amount_candidates(text: str, warnings: list[str]) -> list[str]:
    found: list[str] = []
    lines = text.splitlines()
    foreign = False
    for pattern in AMOUNT_KEYWORDS:
        kw = re.compile(pattern, re.I)
        for i, line in enumerate(lines):
            m = kw.search(line)
            if not m or (_SKIP_LINE.search(line) and "brutto" not in line.lower()):
                continue
            segment = line[m.end():]
            amounts = _AMOUNT.findall(segment)
            if not amounts and i + 1 < len(lines):
                segment = lines[i + 1]
                amounts = _AMOUNT.findall(segment)
            if not amounts:
                continue
            value = parse_amount(amounts[-1])
            if value is None or value <= 0:
                continue
            if _NON_EUR.search(segment) and not re.search(r"EUR|€", segment):
                foreign = True
            s = format_amount(value)
            if s not in found:
                found.append(s)
    if foreign:
        warnings.append("Amount seems to be in a currency other than EUR.")
    return found


def _payee(text: str, iban: str) -> str:
    m = _PAYEE_KEY.search(text)
    if m:
        return m.group(1).strip()
    m = _ANSCHRIFT.search(text)
    if m:
        # "Anschrift: Name" on one line, otherwise the first non-empty line below it
        # same-line text only counts after a colon; otherwise it is a column header row
        rest = m.group(2).strip() if m.group(1) else ""
        if not rest:
            following = text[m.end():].splitlines()
            rest = next((l.strip() for l in following if l.strip()), "")
        name = re.split(r"[ \t]{2,}", rest)[0].strip()
        if name:
            return name
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if iban and iban in iban_mod.normalize(line):
            for prev in reversed(lines[max(0, i - 3):i]):
                prev = prev.strip()
                if prev and re.search(r"[A-Za-zÄÖÜäöü]{3}", prev) and len(prev) <= 70 \
                        and not _NOT_NAME.search(prev) and sum(c.isdigit() for c in prev) < 4:
                    return re.split(r"\s{2,}", prev)[0]
            break
    return ""


def extract_from_text(text: str) -> PaymentData:
    data = PaymentData()
    ibans = iban_mod.find_ibans(text)
    # prefer IBANs introduced by the keyword "IBAN"
    ibans.sort(key=lambda v: 0 if re.search(r"IBAN\W{0,8}" + v[:4], text) else 1)
    data.iban_candidates = ibans
    if ibans:
        data.set("iban", ibans[0], TEXT)
    elif re.search(r"\bIBAN\b", text):
        data.warnings.append("An IBAN keyword was found, but no valid IBAN (checksum).")
    else:
        data.warnings.append("No IBAN found.")

    m = _BIC.search(text)
    if m:
        data.set("bic", m.group(1), TEXT)

    data.amount_candidates = _amount_candidates(text, data.warnings)
    if data.amount_candidates:
        data.set("amount", data.amount_candidates[0], TEXT)
        if len(data.amount_candidates) > 1:
            data.warnings.append("Several amounts found. Check the selection.")
    if len(ibans) > 1:
        data.warnings.append("Several IBANs found. Check the selection.")

    for m in _NUMBER.finditer(text):
        if any(c.isdigit() for c in m.group(1)):
            data.set("remittance", f"Rechnung {m.group(1)}", TEXT)
            break
    data.set("payee", _payee(text, data.iban), TEXT)
    return data
