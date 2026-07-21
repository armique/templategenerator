"""Tests for tracked completed-sale criteria."""

import pytest

from marktwert.domain.money import Money
from marktwert.domain.sales import (
    CompletedSalesCriteria,
    ItemCondition,
    ListingFormat,
    PriceBasis,
    TrackedProduct,
)


def test_criteria_defaults_to_targeted_completed_sales() -> None:
    criteria = CompletedSalesCriteria(query="  RTX   3070 ")

    assert criteria.query == "RTX 3070"
    assert criteria.sold_only is True
    assert criteria.lookback_days == 30
    assert criteria.marketplace_country == "DE"
    assert criteria.currency == "EUR"
    assert criteria.standalone_working_only is True
    assert criteria.conditions == frozenset(ItemCondition)
    assert criteria.listing_formats == frozenset(ListingFormat)
    assert criteria.price_basis is PriceBasis.ITEM_AND_SHIPPING


def test_criteria_normalizes_user_title_filters() -> None:
    criteria = CompletedSalesCriteria(
        query="RTX 3070",
        required_title_terms=("  8 GB ", "8 GB"),
        additional_exclusion_terms=("water block",),
    )

    assert criteria.required_title_terms == ("8 GB",)
    assert criteria.additional_exclusion_terms == ("water block",)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"query": "x"}, "query length"),
        ({"lookback_days": 0}, "lookback_days"),
        ({"lookback_days": 91}, "lookback_days"),
        ({"conditions": frozenset()}, "item condition"),
        ({"listing_formats": frozenset()}, "listing format"),
        ({"category_id": "GPU"}, "category_id"),
        ({"required_title_terms": (" ",)}, "cannot be empty"),
    ],
)
def test_criteria_rejects_invalid_configuration(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CompletedSalesCriteria(query="RTX 3070", **overrides)  # type: ignore[arg-type]


def test_criteria_rejects_inconsistent_price_range() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        CompletedSalesCriteria(
            query="RTX 3070",
            minimum_price=Money.from_major_units("400"),
            maximum_price=Money.from_major_units("300"),
        )


def test_criteria_rejects_price_in_another_currency() -> None:
    with pytest.raises(ValueError, match="currency must match"):
        CompletedSalesCriteria(
            query="RTX 3070",
            maximum_price=Money.from_major_units("300", "USD"),
        )


def test_tracked_product_edit_preserves_identity() -> None:
    product = TrackedProduct.create(
        name="  Main   GPU ",
        criteria=CompletedSalesCriteria(query="RTX 3070"),
    )
    edited = product.edit(
        name="Gaming GPU",
        criteria=CompletedSalesCriteria(
            query="RTX 3070 Gaming",
            maximum_price=Money.from_major_units("350"),
        ),
    )
    disabled = edited.set_enabled(enabled=False)

    assert product.name == "Main GPU"
    assert edited.id == product.id
    assert edited.criteria.maximum_price == Money(minor_units=35_000)
    assert disabled.enabled is False
