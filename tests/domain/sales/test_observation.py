"""Tests for completed-sale observations."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ItemCondition,
    ListingFormat,
    ProductSnapshot,
    SaleObservation,
    SellerSnapshot,
)

SOLD_AT = datetime(2026, 7, 1, 12, tzinfo=UTC)
ACQUIRED_AT = datetime(2026, 7, 2, 8, tzinfo=UTC)


def make_observation(**overrides: object) -> SaleObservation:
    """Create a valid observation with optional field overrides."""
    values: dict[str, object] = {
        "source": "ebay_de",
        "external_item_id": "123456",
        "title": "Gigabyte RTX 3070 Gaming OC",
        "sold_price": Money.from_major_units("299.99"),
        "shipping_price": Money.from_major_units("6.99"),
        "sold_at": SOLD_AT,
        "acquired_at": ACQUIRED_AT,
        "raw_record_hash": "sha256:first",
    }
    values.update(overrides)
    return SaleObservation(**values)  # type: ignore[arg-type]


def test_observation_exposes_identity_and_total_price() -> None:
    observation = make_observation()

    assert observation.identity == ("ebay_de", "123456")
    assert observation.total_price == Money.from_major_units("306.98")


def test_observation_merges_only_missing_optional_facts() -> None:
    original = make_observation(shipping_price=None, location=None)
    incoming = make_observation(
        title="A changed source title",
        sold_price=Money.from_major_units("350"),
        shipping_price=Money.from_major_units("8.49"),
        location="Berlin",
        condition=ItemCondition.USED,
        listing_format=ListingFormat.AUCTION,
        seller=SellerSnapshot(
            name="hardware-shop",
            feedback_percentage=Decimal("99.80"),
            feedback_count=1200,
        ),
        product=ProductSnapshot(brand="Gigabyte", model="RTX 3070"),
        acquired_at=datetime(2026, 7, 3, tzinfo=UTC),
        raw_record_hash="sha256:second",
    )

    merged = original.merge_missing(incoming)

    assert merged.title == original.title
    assert merged.sold_price == original.sold_price
    assert merged.acquired_at == original.acquired_at
    assert merged.raw_record_hash == original.raw_record_hash
    assert merged.shipping_price == Money.from_major_units("8.49")
    assert merged.location == "Berlin"
    assert merged.seller.name == "hardware-shop"
    assert merged.product.model == "RTX 3070"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"source": " "}, "source cannot be empty"),
        ({"sold_price": Money(-1)}, "sold price"),
        ({"shipping_price": Money(-1)}, "shipping price"),
        ({"bid_count": -1}, "bid count"),
        ({"sold_at": datetime(2026, 7, 1)}, "timezone-aware"),
        ({"listing_url": "file:///tmp/item"}, "HTTP or HTTPS"),
    ],
)
def test_observation_rejects_invalid_facts(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        make_observation(**overrides)


def test_observation_rejects_merge_from_another_identity() -> None:
    with pytest.raises(ValueError, match="different identities"):
        make_observation().merge_missing(
            replace(make_observation(), external_item_id="different")
        )
