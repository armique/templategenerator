"""Tests for exact monetary values."""

from decimal import Decimal

import pytest

from marktwert.domain.money import Money


@pytest.mark.parametrize(
    ("major_units", "expected_minor_units"),
    [
        ("0", 0),
        ("99.99", 9_999),
        ("1.005", 101),
        ("-1.005", -101),
    ],
)
def test_money_converts_major_units_without_binary_float(
    major_units: str,
    expected_minor_units: int,
) -> None:
    money = Money.from_major_units(major_units)

    assert money.minor_units == expected_minor_units


def test_money_normalizes_currency_and_exposes_decimal_amount() -> None:
    money = Money(minor_units=12_345, currency=" eur ")

    assert money.currency == "EUR"
    assert money.major_units == Decimal("123.45")


@pytest.mark.parametrize("currency", ["", "EU", "EURO", "€12"])
def test_money_rejects_invalid_currency(currency: str) -> None:
    with pytest.raises(ValueError, match="ISO-4217"):
        Money(minor_units=100, currency=currency)
