from decimal import Decimal as D

import pytest

from giraffe.amounts import format_amount, parse_amount


@pytest.mark.parametrize("raw,expected", [
    ("1.234,56", D("1234.56")),
    ("1,234.56", D("1234.56")),
    ("12,5", D("12.5")),
    ("12.50 €", D("12.50")),
    ("EUR 99,00", D("99.00")),
    ("1.234", D("1234")),
    ("1,234", D("1234")),
    ("0,500", D("0.500")),
    ("1.234.567,89", D("1234567.89")),
    ("1 234,56", D("1234.56")),
    ("1234", D("1234")),
])
def test_parse(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "1,2,3x", "1.2,3.4"])
def test_parse_invalid(raw):
    assert parse_amount(raw) is None


def test_format():
    assert format_amount(D("12.5")) == "12.50"
