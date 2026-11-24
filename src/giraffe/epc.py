"""EPC069-12 QR payload (GiroCode, version 002) and QR rendering."""
import io
import re
from decimal import Decimal

import segno

from . import iban as iban_mod

MAX_BYTES = 331
MAX_NAME = 70
MAX_REFERENCE = 35
MAX_REMITTANCE = 140
MIN_AMOUNT = Decimal("0.01")
MAX_AMOUNT = Decimal("999999999.99")


class EpcError(ValueError):
    """User-presentable validation error."""


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def build_payload(name: str, iban: str, amount: Decimal | None = None, bic: str = "",
                  remittance: str = "", reference: str = "") -> str:
    name, remittance, reference = _clean(name), _clean(remittance), _clean(reference)
    bic = re.sub(r"\s+", "", bic or "").upper()
    iban = iban_mod.normalize(iban)

    if not name:
        raise EpcError("Payee name is missing.")
    if len(name) > MAX_NAME:
        raise EpcError(f"Payee name is too long ({len(name)}/{MAX_NAME} characters).")
    if not iban:
        raise EpcError("IBAN is missing.")
    if not iban_mod.is_valid(iban):
        raise EpcError("IBAN is invalid (checksum or length does not match).")
    if bic and not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?", bic):
        raise EpcError("BIC is invalid.")
    if amount is not None:
        if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
            raise EpcError("Amount must be between 0.01 and 999,999,999.99 EUR.")
    if reference and remittance:
        raise EpcError("Structured reference and remittance text are mutually exclusive.")
    if len(reference) > MAX_REFERENCE:
        raise EpcError(f"Reference is too long ({len(reference)}/{MAX_REFERENCE} characters).")
    if len(remittance) > MAX_REMITTANCE:
        raise EpcError(f"Remittance text is too long ({len(remittance)}/{MAX_REMITTANCE} characters).")

    amount_str = f"EUR{amount.quantize(Decimal('0.01')):.2f}" if amount is not None else ""
    lines = ["BCD", "002", "1", "SCT", bic, name, iban, amount_str, "", reference, remittance, ""]
    while lines and lines[-1] == "":  # trailing empty elements may be omitted (EPC069-12)
        lines.pop()
    payload = "\n".join(lines)
    size = len(payload.encode("utf-8"))
    if size > MAX_BYTES:
        raise EpcError(f"Payload is too large ({size}/{MAX_BYTES} bytes). Shorten name or remittance text.")
    return payload


def make_qr(payload: str) -> segno.QRCode:
    return segno.make(payload, error="m", micro=False, encoding="utf-8")


def png_bytes(payload: str, scale: int = 10) -> bytes:
    buf = io.BytesIO()
    make_qr(payload).save(buf, kind="png", scale=scale, border=4, dark="black", light="white")
    return buf.getvalue()
