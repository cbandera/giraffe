from giraffe.extract.zugferd import parse_xml

CII = b"""<?xml version="1.0"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
 <rsm:ExchangedDocument><ram:ID>RE-2024-17</ram:ID></rsm:ExchangedDocument>
 <rsm:SupplyChainTradeTransaction>
  <ram:ApplicableHeaderTradeAgreement>
   <ram:SellerTradeParty><ram:Name>Muster GmbH</ram:Name></ram:SellerTradeParty>
  </ram:ApplicableHeaderTradeAgreement>
  <ram:ApplicableHeaderTradeSettlement>
   <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
   <ram:SpecifiedTradeSettlementPaymentMeans>
    <ram:PayeePartyCreditorFinancialAccount><ram:IBANID>DE89 3704 0044 0532 0130 00</ram:IBANID></ram:PayeePartyCreditorFinancialAccount>
    <ram:PayeeSpecifiedCreditorFinancialInstitution><ram:BICID>COBADEFFXXX</ram:BICID></ram:PayeeSpecifiedCreditorFinancialInstitution>
   </ram:SpecifiedTradeSettlementPaymentMeans>
   <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    <ram:GrandTotalAmount>119.00</ram:GrandTotalAmount>
    <ram:DuePayableAmount>100.00</ram:DuePayableAmount>
   </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
  </ram:ApplicableHeaderTradeSettlement>
 </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""

UBL = b"""<?xml version="1.0"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
 <cbc:ID>INV-9</cbc:ID>
 <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
 <cac:AccountingSupplierParty><cac:Party><cac:PartyName><cbc:Name>Beispiel AG</cbc:Name></cac:PartyName></cac:Party></cac:AccountingSupplierParty>
 <cac:PaymentMeans><cbc:PaymentID>PAY-1</cbc:PaymentID>
  <cac:PayeeFinancialAccount><cbc:ID>DE89370400440532013000</cbc:ID></cac:PayeeFinancialAccount></cac:PaymentMeans>
 <cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="EUR">42.50</cbc:PayableAmount></cac:LegalMonetaryTotal>
</Invoice>"""


def test_cii():
    d = parse_xml(CII)
    assert (d.payee, d.iban, d.bic, d.amount, d.currency, d.remittance) == (
        "Muster GmbH", "DE89370400440532013000", "COBADEFFXXX", "100.00", "EUR", "Rechnung RE-2024-17")
    assert d.source("iban") == "e-invoice"


def test_ubl():
    d = parse_xml(UBL)
    assert (d.payee, d.iban, d.amount, d.remittance) == ("Beispiel AG", "DE89370400440532013000", "42.50", "PAY-1")


def test_garbage_and_xxe():
    assert parse_xml(b"not xml") is None
    assert parse_xml(b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><a>&x;</a>') is None


def test_pdf_with_embedded_xml(tmp_path):
    from pypdf import PdfWriter

    from giraffe.extract import from_file
    w = PdfWriter()
    w.add_blank_page(200, 200)
    w.add_attachment("factur-x.xml", CII)
    path = tmp_path / "inv.pdf"
    with open(path, "wb") as f:
        w.write(f)
    d = from_file(str(path))
    assert d.iban == "DE89370400440532013000" and d.source("iban") == "e-invoice"
