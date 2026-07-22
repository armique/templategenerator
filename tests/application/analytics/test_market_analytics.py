"""Numerical integration tests for local market analysis."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from marktwert.application.analytics import (
    AnalysisWindow,
    AnalyzeMarket,
    MarketAnalyticsService,
)
from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ClassificationDecision,
    ClassificationResult,
    CompletedSalesCriteria,
    SaleObservation,
    TrackedProduct,
)
from marktwert.infrastructure.persistence import (
    SqlAlchemyUnitOfWork,
    create_sqlite_engine,
    upgrade_database,
)

NOW = datetime(2026, 7, 22, 12, tzinfo=UTC)


def test_analytics_calculates_accepted_sales_and_history(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "analytics.db")
    upgrade_database(engine)
    factory = SqlAlchemyUnitOfWork.factory_for(engine)
    product = TrackedProduct.create(
        "Test GPU",
        CompletedSalesCriteria(query="Test GPU"),
    )
    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(product)
        for index, price in enumerate(("100", "200", "300"), start=1):
            observation = SaleObservation(
                source="fixture",
                external_item_id=str(index),
                title=f"Test GPU {index}",
                sold_price=Money.from_major_units(price),
                shipping_price=Money.from_major_units("5"),
                sold_at=NOW - timedelta(days=4 - index),
                acquired_at=NOW,
                raw_record_hash=f"hash-{index}",
            )
            unit_of_work.sale_observations.upsert(
                observation,
                matched_product_id=product.id,
            )
        excluded = SaleObservation(
            source="fixture",
            external_item_id="excluded",
            title="Test GPU empty box",
            sold_price=Money.from_major_units("10"),
            sold_at=NOW - timedelta(days=1),
            acquired_at=NOW,
            raw_record_hash="hash-excluded",
        )
        unit_of_work.sale_observations.upsert(
            excluded,
            matched_product_id=product.id,
            classification=ClassificationResult(ClassificationDecision.EXCLUDE),
        )
        unit_of_work.commit()

    analysis = MarketAnalyticsService(factory, clock=lambda: NOW).analyze(
        AnalyzeMarket(product.id, AnalysisWindow.DAYS_30)
    )

    statistics = analysis.statistics
    assert statistics is not None
    assert statistics.sample_size == 3
    assert statistics.average == Money.from_major_units("205")
    assert statistics.median == Money.from_major_units("205")
    assert statistics.minimum == Money.from_major_units("105")
    assert statistics.maximum == Money.from_major_units("305")
    assert statistics.standard_deviation == Money.from_major_units("100")
    assert statistics.average_shipping == Money.from_major_units("5")
    assert statistics.average_daily_sales == 1
    assert statistics.average_weekly_sales == 7
    assert statistics.trend_percent is not None
    assert len(analysis.history) == 3
    assert analysis.history[1].moving_average == Money.from_major_units("155")
    engine.dispose()


def test_analytics_returns_empty_result_for_window_without_sales(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "empty-analytics.db")
    upgrade_database(engine)
    factory = SqlAlchemyUnitOfWork.factory_for(engine)
    product = TrackedProduct.create(
        "No sales",
        CompletedSalesCriteria(query="No sales"),
    )
    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(product)
        unit_of_work.commit()

    analysis = MarketAnalyticsService(factory, clock=lambda: NOW).analyze(
        AnalyzeMarket(product.id, AnalysisWindow.DAYS_7)
    )

    assert analysis.statistics is None
    assert analysis.history == ()
    engine.dispose()
