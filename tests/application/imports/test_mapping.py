"""Tests for German and English completed-sales row mapping."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from marktwert.application.imports.mapping import (
    RowValidationError,
    SalesRowMapper,
)
from marktwert.application.imports.models import ImportIssueCode, RawSalesRow
from marktwert.domain.money import Money
from marktwert.domain.sales import ItemCondition, ListingFormat

ACQUIRED_AT = datetime(2026, 7, 22, 12, tzinfo=UTC)


def test_mapper_accepts_german_headers_and_number_formats() -> None:
    mapper = SalesRowMapper("Europe/Berlin")
    row = RawSalesRow(
        row_number=2,
        values={
            "artikelnummer": "123456",
            "titel": "Gigabyte RTX 3070 Gaming OC 8 GB",
            "verkaufspreis": "1.234,56 €",
            "versandkosten": "6,99",
            "verkauft_am": "21.07.2026 20:15",
            "zustand": "Gebraucht",
            "angebotsformat": "Sofort-Kaufen",
            "preisvorschlag": "ja",
            "gebote": "0",
            "verkäuferbewertung": "99,8 %",
        },
    )

    observation = mapper.map(
        row,
        source="manual_export",
        acquired_at=ACQUIRED_AT,
    )

    assert observation.external_item_id == "123456"
    assert observation.sold_price == Money.from_major_units("1234.56")
    assert observation.shipping_price == Money.from_major_units("6.99")
    assert observation.sold_at == datetime(2026, 7, 21, 18, 15, tzinfo=UTC)
    assert observation.condition is ItemCondition.USED
    assert observation.listing_format is ListingFormat.BUY_IT_NOW
    assert observation.best_offer is True
    assert observation.seller.feedback_percentage == Decimal("99.8")
    assert len(observation.raw_record_hash) == 64


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("299.99", 29_999),
        ("299,99", 29_999),
        ("1,299.99", 129_999),
        ("1.299,99", 129_999),
        (300, 30_000),
    ],
)
def test_mapper_supports_common_price_representations(
    value: object,
    expected: int,
) -> None:
    observation = SalesRowMapper("UTC").map(
        RawSalesRow(
            row_number=2,
            values={
                "item_id": "item-1",
                "title": "RTX 3070",
                "sold_price": value,
                "sold_at": "2026-07-21",
            },
        ),
        source="test",
        acquired_at=ACQUIRED_AT,
    )

    assert observation.sold_price.minor_units == expected


def test_mapper_reports_missing_required_schema_fields() -> None:
    missing = SalesRowMapper("UTC").missing_required_fields(
        {"item_id", "title", "price"}
    )

    assert missing == ("sold_at",)


def test_mapper_rejects_invalid_row_value() -> None:
    with pytest.raises(RowValidationError) as error:
        SalesRowMapper("UTC").map(
            RawSalesRow(
                row_number=2,
                values={
                    "item_id": "item-1",
                    "title": "RTX 3070",
                    "sold_price": "not money",
                    "sold_at": "2026-07-21",
                },
            ),
            source="test",
            acquired_at=ACQUIRED_AT,
        )

    assert error.value.code is ImportIssueCode.INVALID_VALUE
    assert str(error.value) == "sold_price is not a valid monetary amount"
