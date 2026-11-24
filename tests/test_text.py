from giraffe.extract.text import extract_from_text

INVOICE = """
Muster GmbH
Musterstraße 1, 12345 Musterstadt

Rechnung Nr. 2024-0815
Datum: 01.02.2024

Pos  Beschreibung          Menge   Preis
1    Beratung              10      100,00

Zwischensumme netto                 1.000,00
zzgl. 19 % MwSt.                      190,00
Rechnungsbetrag                    1.190,00 EUR

Bitte überweisen Sie den Betrag innerhalb von 14 Tagen.

Muster GmbH            Bank: Testbank            IBAN: DE89 3704 0044 0532 0130 00
                       BIC: COBADEFFXXX
"""


def test_basic():
    d = extract_from_text(INVOICE)
    assert d.iban == "DE89370400440532013000"
    assert d.bic == "COBADEFFXXX"
    assert d.amount == "1190.00"
    assert d.remittance == "Rechnung 2024-0815"
    assert d.source("amount") == "text"


def test_zu_zahlen_beats_total():
    d = extract_from_text("Gesamtbetrag 100,00\nZu zahlen: 80,00 EUR\nDE89 3704 0044 0532 0130 00")
    assert d.amount == "80.00"
    assert d.amount_candidates == ["80.00", "100.00"]


def test_english_format_and_multiple_ibans():
    d = extract_from_text("Invoice No: INV-77\nAmount due: 1,234.50\nIBAN DE89370400440532013000\nIBAN GB82 WEST 1234 5698 7654 32")
    assert d.amount == "1234.50"
    assert len(d.iban_candidates) == 2
    assert d.remittance == "Rechnung INV-77"


def test_payee_keyword():
    d = extract_from_text("Kontoinhaber: Hans Meier    Sparkasse\nIBAN DE89370400440532013000")
    assert d.payee == "Hans Meier"


def test_no_iban_warns():
    d = extract_from_text("nothing here")
    assert d.iban == "" and d.warnings


def test_foreign_currency_warns():
    d = extract_from_text("Total due: 100.00 USD\nDE89370400440532013000")
    assert any("currency" in w for w in d.warnings)


def test_payee_keyword_end_of_line():
    d = extract_from_text("Kontoinhaber: Muster GmbH\nIBAN DE89370400440532013000")
    assert d.payee == "Muster GmbH"


def test_payee_anschrift_next_line():
    d = extract_from_text("Anschrift\nMuster GmbH\nMusterstr. 1\n12345 Stadt\nIBAN DE89370400440532013000")
    assert d.payee == "Muster GmbH"


def test_payee_anschrift_same_line_and_columns():
    d = extract_from_text("Anschrift: Muster GmbH    Telefon 123\nIBAN DE89370400440532013000")
    assert d.payee == "Muster GmbH"


def test_payee_anschrift_footer_columns():
    t = ("Anschrift                      Bankverbindung                Kontakt\n"
         "Muster Sanitär&Heizung         DE89 3704 0044 0532 0130 00   +49 123\n"
         "Musterstr. 74\n")
    assert extract_from_text(t).payee == "Muster Sanitär&Heizung"
