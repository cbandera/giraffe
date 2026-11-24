from decimal import Decimal as D

import pytest

from giraffe import epc

IBAN = "DE89 3704 0044 0532 0130 00"


def test_golden():
    payload = epc.build_payload("Max Mustermann GmbH", IBAN, D("119"), "COBADEFFXXX", "Rechnung 2024-001")
    assert payload == (
        "BCD\n002\n1\nSCT\nCOBADEFFXXX\nMax Mustermann GmbH\nDE89370400440532013000\n"
        "EUR119.00\n\n\nRechnung 2024-001"
    )


def test_no_amount_no_bic_trailing_stripped():
    payload = epc.build_payload("A", IBAN)
    assert payload == "BCD\n002\n1\nSCT\n\nA\nDE89370400440532013000"


def test_reference_instead_of_remittance():
    payload = epc.build_payload("A", IBAN, D("1"), reference="RF18539007547034")
    assert payload.split("\n")[9] == "RF18539007547034"


def test_exclusive():
    with pytest.raises(epc.EpcError):
        epc.build_payload("A", IBAN, reference="RF18", remittance="x")


@pytest.mark.parametrize("kwargs", [
    dict(name="x" * 71),
    dict(name="A", remittance="x" * 141),
    dict(name="A", reference="x" * 36),
    dict(name=""),
    dict(name="A", amount=D("0")),
    dict(name="A", amount=D("1000000000")),
    dict(name="A", bic="XX"),
])
def test_limits(kwargs):
    kwargs.setdefault("amount", None)
    name = kwargs.pop("name")
    with pytest.raises(epc.EpcError):
        epc.build_payload(name, IBAN, **kwargs)


def test_invalid_iban():
    with pytest.raises(epc.EpcError):
        epc.build_payload("A", "DE89 3704 0044 0532 0130 01")


def test_byte_limit_with_multibyte():
    # 70 chars of 3-byte characters + 140 chars of 3-byte characters exceeds 331 bytes
    with pytest.raises(epc.EpcError, match="bytes"):
        epc.build_payload("€" * 70, IBAN, D("1"), remittance="€" * 140)


def test_umlauts_ok():
    payload = epc.build_payload("Müller & Söhne", IBAN, remittance="Rechnung Nr. 5 äöüß")
    assert "Müller & Söhne" in payload
    assert epc.png_bytes(payload).startswith(b"\x89PNG")
