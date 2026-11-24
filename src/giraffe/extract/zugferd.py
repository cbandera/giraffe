"""Read payment data from embedded e-invoice XML (ZUGFeRD / Factur-X / XRechnung)."""
import io

import defusedxml.ElementTree as ET
from pypdf import PdfReader

from .. import iban as iban_mod
from ..amounts import format_amount, parse_amount
from .models import E_INVOICE, PaymentData

MAX_XML_BYTES = 5 * 1024 * 1024
KNOWN_NAMES = {"factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml", "ZUGFeRD-invoice.xml".lower()}


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _find(el, *names):
    """First descendant named names[0], then direct children along the rest."""
    cur = next((e for e in el.iter() if _local(e.tag) == names[0]), None)
    for n in names[1:]:
        if cur is None:
            return None
        cur = next((c for c in cur if _local(c.tag) == n), None)
    return cur


def _text(el, *names) -> str:
    found = _find(el, *names)
    return (found.text or "").strip() if found is not None else ""


def parse_xml(xml: bytes) -> PaymentData | None:
    try:
        root = ET.fromstring(xml)
    except Exception:
        return None
    kind = _local(root.tag)
    data = PaymentData()
    if kind == "CrossIndustryInvoice":
        data.set("payee", _text(root, "SellerTradeParty", "Name"), E_INVOICE)
        data.set("iban", iban_mod.normalize(_text(root, "PayeePartyCreditorFinancialAccount", "IBANID")), E_INVOICE)
        data.set("bic", _text(root, "PayeeSpecifiedCreditorFinancialInstitution", "BICID"), E_INVOICE)
        amount = _text(root, "DuePayableAmount") or _text(root, "GrandTotalAmount")
        number = _text(root, "ExchangedDocument", "ID")
        reference = _text(root, "PaymentReference")
        currency = _text(root, "InvoiceCurrencyCode")
    elif kind in ("Invoice", "CreditNote"):
        data.set("payee", _text(root, "PayeeParty", "PartyName", "Name")
                 or _text(root, "AccountingSupplierParty", "Party", "PartyName", "Name")
                 or _text(root, "AccountingSupplierParty", "Party", "PartyLegalEntity", "RegistrationName"), E_INVOICE)
        data.set("iban", iban_mod.normalize(_text(root, "PayeeFinancialAccount", "ID")), E_INVOICE)
        data.set("bic", _text(root, "PayeeFinancialAccount", "FinancialInstitutionBranch", "ID"), E_INVOICE)
        amount = _text(root, "LegalMonetaryTotal", "PayableAmount")
        number = next(((c.text or "").strip() for c in root if _local(c.tag) == "ID"), "")
        reference = _text(root, "PaymentID")
        currency = _text(root, "DocumentCurrencyCode")
    else:
        return None

    parsed = parse_amount(amount)
    if parsed is not None:
        data.set("amount", format_amount(parsed), E_INVOICE)
    if currency:
        data.currency = currency.upper()
    data.set("remittance", reference or (f"Rechnung {number}" if number else ""), E_INVOICE)
    if data.iban:
        data.iban_candidates = [data.iban]
    if data.amount:
        data.amount_candidates = [data.amount]
    return data if data.iban else None


def extract_from_pdf(path: str) -> PaymentData | None:
    try:
        reader = PdfReader(path)
        attachments = reader.attachments
    except Exception:
        return None
    for name, blobs in attachments.items():
        if not name.lower().endswith(".xml"):
            continue
        for blob in blobs:
            if len(blob) > MAX_XML_BYTES:
                continue
            data = parse_xml(blob)
            if data is not None:
                return data
    return None
