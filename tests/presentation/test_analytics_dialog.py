"""Tests for asynchronous market-analysis presentation."""

from datetime import UTC, date, datetime
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from marktwert.application.analytics import (
    AnalyzeMarket,
    MarketAnalysis,
    MarketStatistics,
    PriceHistoryPoint,
)
from marktwert.domain.money import Money
from marktwert.domain.sales import CompletedSalesCriteria, TrackedProduct
from marktwert.presentation.analytics_dialog import MarketAnalysisDialog
from marktwert.presentation.analytics_view_model import AnalyticsViewModel


class FakeProductService:
    """Return one selectable tracked product."""

    def __init__(self, product: TrackedProduct) -> None:
        self._product = product

    def list_all(self) -> tuple[TrackedProduct, ...]:
        """Return a deterministic product collection."""
        return (self._product,)


class FakeAnalyticsService:
    """Return deterministic chart-ready statistics."""

    def analyze(self, request: AnalyzeMarket) -> MarketAnalysis:
        """Build a representative market analysis."""
        sold_at = datetime(2026, 7, 20, 12, tzinfo=UTC)
        statistics = MarketStatistics(
            sample_size=2,
            average=Money.from_major_units("205"),
            median=Money.from_major_units("205"),
            minimum=Money.from_major_units("105"),
            maximum=Money.from_major_units("305"),
            standard_deviation=Money.from_major_units("100"),
            average_shipping=Money.from_major_units("5"),
            average_daily_sales=Decimal("1"),
            average_weekly_sales=Decimal("7"),
            average_monthly_sales=Decimal("30.4375"),
            trend_percent=Decimal("10"),
            volatility_percent=Decimal("20"),
            first_sale_date=date(2026, 7, 19),
            last_sale_date=date(2026, 7, 20),
        )
        history = (
            PriceHistoryPoint(
                sold_at=sold_at,
                price=Money.from_major_units("105"),
                moving_average=Money.from_major_units("105"),
            ),
            PriceHistoryPoint(
                sold_at=sold_at,
                price=Money.from_major_units("305"),
                moving_average=Money.from_major_units("205"),
            ),
        )
        return MarketAnalysis(request, statistics, history)


def test_dialog_loads_products_and_renders_analysis(qtbot: QtBot) -> None:
    product = TrackedProduct.create(
        "RTX 3070",
        CompletedSalesCriteria(query="RTX 3070"),
    )
    view_model = AnalyticsViewModel(
        FakeAnalyticsService(),  # type: ignore[arg-type]
        FakeProductService(product),  # type: ignore[arg-type]
    )
    dialog = MarketAnalysisDialog(view_model)
    qtbot.addWidget(dialog)
    dialog.show()
    analyze = dialog.findChild(QPushButton, "analyzeButton")
    average = dialog.findChild(QLabel, "metricAverage")
    qtbot.waitUntil(analyze.isEnabled)

    qtbot.mouseClick(analyze, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: average.text() != "—")

    assert average.text() == "205.00 EUR"
    view_model.shutdown()
