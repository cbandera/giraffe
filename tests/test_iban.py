from giraffe import iban


def test_valid():
    assert iban.is_valid("DE89 3704 0044 0532 0130 00")
    assert iban.is_valid("de89370400440532013000")
    assert iban.is_valid("GB82 WEST 1234 5698 7654 32")


def test_invalid():
    assert not iban.is_valid("DE89 3704 0044 0532 0130 01")
    assert not iban.is_valid("DE89 3704 0044 0532 0130 0")  # wrong length
    assert not iban.is_valid("")
    assert not iban.is_valid("hello")


def test_find_trims_trailing_words():
    text = "IBAN: DE89 3704 0044 0532 0130 00 BIC COBADEFFXXX"
    assert iban.find_ibans(text) == ["DE89370400440532013000"]


def test_find_ignores_invalid():
    assert iban.find_ibans("DE89 3704 0044 0532 0130 01") == []
