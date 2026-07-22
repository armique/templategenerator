"""Typed market-analysis inputs and outputs."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from marktwert.domain.money import Money
from marktwert.domain.sales import TrackedProductId


class AnalysisWindow(StrEnum):
    """Supported historical analysis windows."""

    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    DAYS_180 = "180d"
    DAYS_365 = "365d"
    ALL_TIME = "all"

    @property
    def days(self) -> int | None:
        """Return the bounded day count or none for all time."""
        return {
            self.DAYS_7: 7,
            self.DAYS_30: 30,
            self.DAYS_90: 90,
            self.DAYS_180: 180,
            self.DAYS_365: 365,
            self.ALL_TIME: None,
        }[self]


@dataclass(frozen=True, slots=True)
class AnalyzeMarket:
    """Request statistics for one tracked product."""

    product_id: TrackedProductId
    window: AnalysisWindow = AnalysisWindow.DAYS_30
    include_shipping: bool = True


@dataclass(frozen=True, slots=True)
class SaleAnalyticsPoint:
    """Minimal accepted-sale projection used by numerical analysis."""

    sold_at: datetime
    sold_price_minor: int
    shipping_price_minor: int | None
    currency: str


@dataclass(frozen=True, slots=True)
class PriceHistoryPoint:
    """A sold observation and its seven-day moving average."""

    sold_at: datetime
    price: Money
    moving_average: Money


@dataclass(frozen=True, slots=True)
class MarketStatistics:
    """Reproducible descriptive market statistics."""

    sample_size: int
    average: Money
    median: Money
    minimum: Money
    maximum: Money
    standard_deviation: Money
    average_shipping: Money
    average_daily_sales: Decimal
    average_weekly_sales: Decimal
    average_monthly_sales: Decimal
    trend_percent: Decimal | None
    volatility_percent: Decimal
    first_sale_date: date
    last_sale_date: date


@dataclass(frozen=True, slots=True)
class MarketAnalysis:
    """Statistics and chart-ready history for one request."""

    request: AnalyzeMarket
    statistics: MarketStatistics | None
    history: tuple[PriceHistoryPoint, ...]
