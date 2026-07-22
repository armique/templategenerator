"""Exact purchase-price recommendation policy."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from marktwert.domain.money import Money

BASIS_POINTS_PER_PERCENT = 100
FULL_RATE_BASIS_POINTS = 10_000


@dataclass(frozen=True, slots=True)
class RecommendationAssumptions:
    """Immutable revenue, fee, cost, and desired-profit assumptions."""

    expected_sale_price: Money
    desired_profit_basis_points: int
    marketplace_fee_basis_points: int
    fixed_marketplace_fee: Money
    outbound_shipping: Money
    other_costs: Money

    def __post_init__(self) -> None:
        """Validate rates, currencies, and non-negative costs."""
        if not 0 <= self.desired_profit_basis_points < FULL_RATE_BASIS_POINTS:
            message = "desired profit must be between 0% and 99.99%"
            raise ValueError(message)
        if not 0 <= self.marketplace_fee_basis_points < FULL_RATE_BASIS_POINTS:
            message = "marketplace fee must be between 0% and 99.99%"
            raise ValueError(message)
        costs = (
            self.fixed_marketplace_fee,
            self.outbound_shipping,
            self.other_costs,
        )
        if any(cost.currency != self.expected_sale_price.currency for cost in costs):
            message = "all recommendation money must use one currency"
            raise ValueError(message)
        if self.expected_sale_price.minor_units < 0 or any(
            cost.minor_units < 0 for cost in costs
        ):
            message = "recommendation values cannot be negative"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class PurchaseRecommendation:
    """Calculated acquisition ceiling and expected economics."""

    assumptions: RecommendationAssumptions
    maximum_purchase_price: Money
    expected_fees: Money
    expected_profit: Money
    roi_percent: Decimal | None
    feasible: bool


class PurchaseRecommendationPolicy:
    """Calculate a reproducible maximum purchase price."""

    def calculate(
        self,
        assumptions: RecommendationAssumptions,
    ) -> PurchaseRecommendation:
        """Calculate fees, target profit, acquisition ceiling, and ROI."""
        currency = assumptions.expected_sale_price.currency
        revenue = assumptions.expected_sale_price.minor_units
        variable_fee = _rate_amount(
            revenue,
            assumptions.marketplace_fee_basis_points,
        )
        fees = variable_fee + assumptions.fixed_marketplace_fee.minor_units
        target_profit = _rate_amount(
            revenue,
            assumptions.desired_profit_basis_points,
        )
        maximum_purchase = (
            revenue
            - fees
            - assumptions.outbound_shipping.minor_units
            - assumptions.other_costs.minor_units
            - target_profit
        )
        feasible = maximum_purchase > 0
        bounded_purchase = max(0, maximum_purchase)
        expected_profit = (
            revenue
            - bounded_purchase
            - fees
            - assumptions.outbound_shipping.minor_units
            - assumptions.other_costs.minor_units
        )
        roi = (
            (Decimal(expected_profit) / Decimal(bounded_purchase) * Decimal(100))
            if bounded_purchase
            else None
        )
        return PurchaseRecommendation(
            assumptions=assumptions,
            maximum_purchase_price=Money(bounded_purchase, currency),
            expected_fees=Money(fees, currency),
            expected_profit=Money(expected_profit, currency),
            roi_percent=(
                roi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if roi is not None
                else None
            ),
            feasible=feasible,
        )


def _rate_amount(minor_units: int, basis_points: int) -> int:
    return int(
        (Decimal(minor_units) * Decimal(basis_points) / FULL_RATE_BASIS_POINTS)
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
