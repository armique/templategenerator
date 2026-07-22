"""Tests for exact purchase-price recommendations."""

from decimal import Decimal

from marktwert.domain.money import Money
from marktwert.domain.recommendation import (
    PurchaseRecommendationPolicy,
    RecommendationAssumptions,
)


def test_policy_calculates_maximum_purchase_and_roi() -> None:
    assumptions = RecommendationAssumptions(
        expected_sale_price=Money.from_major_units("1000"),
        desired_profit_basis_points=2500,
        marketplace_fee_basis_points=1300,
        fixed_marketplace_fee=Money.from_major_units("0.35"),
        outbound_shipping=Money.from_major_units("10"),
        other_costs=Money.from_major_units("20"),
    )

    result = PurchaseRecommendationPolicy().calculate(assumptions)

    assert result.maximum_purchase_price == Money.from_major_units("589.65")
    assert result.expected_fees == Money.from_major_units("130.35")
    assert result.expected_profit == Money.from_major_units("250")
    assert result.roi_percent is not None
    assert result.roi_percent == Decimal("42.40")
    assert result.feasible is True


def test_policy_marks_unprofitable_assumptions_as_infeasible() -> None:
    result = PurchaseRecommendationPolicy().calculate(
        RecommendationAssumptions(
            expected_sale_price=Money.from_major_units("10"),
            desired_profit_basis_points=5000,
            marketplace_fee_basis_points=2000,
            fixed_marketplace_fee=Money.from_major_units("2"),
            outbound_shipping=Money.from_major_units("5"),
            other_costs=Money.from_major_units("5"),
        )
    )

    assert result.maximum_purchase_price == Money(0)
    assert result.expected_profit.minor_units < 0
    assert result.roi_percent is None
    assert result.feasible is False
