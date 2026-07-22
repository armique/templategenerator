"""Numerical market statistics and price-history analysis."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections.abc import Callable

import numpy as np
import pandas as pd

from marktwert.application.analytics.models import (
    AnalyzeMarket,
    MarketAnalysis,
    MarketStatistics,
    PriceHistoryPoint,
    SaleAnalyticsPoint,
)
from marktwert.application.ports import UnitOfWorkFactory
from marktwert.domain.money import Money

MOVING_AVERAGE_WINDOW = "7D"
MONTH_DAYS = Decimal("30.4375")
RATE_QUANTUM = Decimal("0.0001")


class MarketAnalyticsService:
    """Calculate robust local market metrics from accepted sales."""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize repository access and an injectable UTC clock."""
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or _utc_now

    def analyze(self, request: AnalyzeMarket) -> MarketAnalysis:
        """Calculate statistics and a seven-day moving-average history."""
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            message = "analytics clock must return a timezone-aware datetime"
            raise ValueError(message)
        sold_from = (
            now - timedelta(days=request.window.days)
            if request.window.days is not None
            else None
        )
        with self._unit_of_work_factory() as unit_of_work:
            points = unit_of_work.market_analytics.list_accepted(
                request.product_id,
                sold_from=sold_from,
            )
        if not points:
            return MarketAnalysis(request=request, statistics=None, history=())

        currencies = {point.currency for point in points}
        if len(currencies) != 1:
            message = "market analysis requires a single currency"
            raise ValueError(message)
        currency = currencies.pop()
        prices = np.asarray(
            [
                point.sold_price_minor
                + (
                    point.shipping_price_minor or 0
                    if request.include_shipping
                    else 0
                )
                for point in points
            ],
            dtype=np.float64,
        )
        shipping = np.asarray(
            [point.shipping_price_minor or 0 for point in points],
            dtype=np.float64,
        )
        sold_dates = [point.sold_at for point in points]
        day_span = max(1, (sold_dates[-1].date() - sold_dates[0].date()).days + 1)
        daily_rate = Decimal(len(points)) / Decimal(day_span)
        mean = float(np.mean(prices))
        standard_deviation = (
            float(np.std(prices, ddof=1)) if len(prices) > 1 else 0.0
        )
        trend = _trend_percent(prices, sold_dates, mean)
        volatility = (
            Decimal(str(standard_deviation / mean * 100)) if mean else Decimal(0)
        )
        statistics = MarketStatistics(
            sample_size=len(points),
            average=_money(mean, currency),
            median=_money(float(np.median(prices)), currency),
            minimum=_money(float(np.min(prices)), currency),
            maximum=_money(float(np.max(prices)), currency),
            standard_deviation=_money(standard_deviation, currency),
            average_shipping=_money(float(np.mean(shipping)), currency),
            average_daily_sales=_rate(daily_rate),
            average_weekly_sales=_rate(daily_rate * Decimal(7)),
            average_monthly_sales=_rate(daily_rate * MONTH_DAYS),
            trend_percent=_rate(trend) if trend is not None else None,
            volatility_percent=_rate(volatility),
            first_sale_date=sold_dates[0].date(),
            last_sale_date=sold_dates[-1].date(),
        )
        history = _history(points, prices, currency)
        return MarketAnalysis(
            request=request,
            statistics=statistics,
            history=history,
        )


def _history(
    points: tuple[SaleAnalyticsPoint, ...],
    prices: np.ndarray,
    currency: str,
) -> tuple[PriceHistoryPoint, ...]:
    frame = pd.DataFrame(
        {"price": prices},
        index=pd.DatetimeIndex([point.sold_at for point in points]),
    ).sort_index()
    moving = frame["price"].rolling(MOVING_AVERAGE_WINDOW, min_periods=1).mean()
    return tuple(
        PriceHistoryPoint(
            sold_at=index.to_pydatetime(),
            price=_money(float(price), currency),
            moving_average=_money(float(moving.iloc[position]), currency),
        )
        for position, (index, price) in enumerate(frame["price"].items())
    )


def _trend_percent(
    prices: np.ndarray,
    sold_dates: list[datetime],
    mean: float,
) -> Decimal | None:
    if len(prices) < 3 or sold_dates[-1] == sold_dates[0] or mean == 0:
        return None
    x_values = np.asarray(
        [
            (sold_at - sold_dates[0]).total_seconds() / 86_400
            for sold_at in sold_dates
        ],
        dtype=np.float64,
    )
    slope = float(np.polyfit(x_values, prices, 1)[0])
    duration = float(x_values[-1] - x_values[0])
    return Decimal(str(slope * duration / mean * 100))


def _money(value: float, currency: str) -> Money:
    minor_units = int(
        Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return Money(minor_units=minor_units, currency=currency)


def _rate(value: Decimal) -> Decimal:
    return value.quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def _utc_now() -> datetime:
    return datetime.now(UTC)
