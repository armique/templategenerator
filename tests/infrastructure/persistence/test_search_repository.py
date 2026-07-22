"""Integration tests for indexed local completed-sales search."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from marktwert.application.search import (
    SaleSearchFilters,
    SearchSales,
    SearchSalesService,
)
from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ClassificationDecision,
    ClassificationEvidence,
    ClassificationResult,
    CompletedSalesCriteria,
    ExclusionReason,
    ItemCondition,
    ListingFormat,
    SaleObservation,
    TrackedProduct,
)
from marktwert.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

BASE_TIME = datetime(2026, 7, 20, 12, tzinfo=UTC)


def make_observation(
    item_id: str,
    title: str,
    price: str,
    *,
    days_ago: int,
) -> SaleObservation:
    """Create an indexed completed-sale observation."""
    return SaleObservation(
        source="search-fixture",
        external_item_id=item_id,
        title=title,
        sold_price=Money.from_major_units(price),
        shipping_price=Money.from_major_units("5"),
        sold_at=BASE_TIME - timedelta(days=days_ago),
        acquired_at=BASE_TIME,
        raw_record_hash=f"hash-{item_id}",
        condition=ItemCondition.USED,
        listing_format=ListingFormat.BUY_IT_NOW,
    )


def seed_search_data(sqlite_engine: Engine) -> TrackedProduct:
    """Persist accepted, excluded, and review search fixtures."""
    factory = SqlAlchemyUnitOfWork.factory_for(sqlite_engine)
    product = TrackedProduct.create(
        "Graphics cards",
        CompletedSalesCriteria(query="RTX 3070"),
    )
    classifications = (
        (
            make_observation(
                "1",
                "Gigabyte GeForce RTX 3070 Gaming OC",
                "300",
                days_ago=1,
            ),
            ClassificationResult(ClassificationDecision.ACCEPT),
        ),
        (
            make_observation("2", "RTX 3070 nur OVP", "20", days_ago=2),
            ClassificationResult(
                ClassificationDecision.EXCLUDE,
                (
                    ClassificationEvidence(
                        ExclusionReason.EMPTY_BOX,
                        "nur ovp",
                    ),
                ),
            ),
        ),
        (
            make_observation("3", "RTX 3070 ungeprüft", "180", days_ago=3),
            ClassificationResult(ClassificationDecision.REVIEW),
        ),
        (
            make_observation("4", "AMD Ryzen 5700X", "140", days_ago=4),
            ClassificationResult(ClassificationDecision.ACCEPT),
        ),
    )
    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(product)
        for observation, classification in classifications:
            unit_of_work.sale_observations.upsert(
                observation,
                matched_product_id=product.id,
                classification=classification,
            )
        unit_of_work.commit()
    return product


def test_fts_search_defaults_to_accepted_sales(sqlite_engine: Engine) -> None:
    product = seed_search_data(sqlite_engine)
    service = SearchSalesService(SqlAlchemyUnitOfWork.factory_for(sqlite_engine))

    page = service.search(
        SearchSales(
            query="rtx 3070",
            filters=SaleSearchFilters(tracked_product_id=product.id),
        )
    )

    assert [item.external_item_id for item in page.items] == ["1"]
    assert page.items[0].total_price == Money.from_major_units("305")


def test_search_can_show_excluded_and_review_rows(sqlite_engine: Engine) -> None:
    product = seed_search_data(sqlite_engine)
    service = SearchSalesService(SqlAlchemyUnitOfWork.factory_for(sqlite_engine))

    page = service.search(
        SearchSales(
            query="RTX",
            filters=SaleSearchFilters(
                tracked_product_id=product.id,
                classifications=frozenset(
                    {
                        ClassificationDecision.EXCLUDE,
                        ClassificationDecision.REVIEW,
                    }
                ),
            ),
        )
    )

    assert [item.external_item_id for item in page.items] == ["2", "3"]
    assert {item.classification for item in page.items} == {
        ClassificationDecision.EXCLUDE,
        ClassificationDecision.REVIEW,
    }


def test_search_uses_stable_keyset_pagination_and_price_filter(
    sqlite_engine: Engine,
) -> None:
    seed_search_data(sqlite_engine)
    service = SearchSalesService(SqlAlchemyUnitOfWork.factory_for(sqlite_engine))
    filters = SaleSearchFilters(
        minimum_price=Money.from_major_units("100"),
        maximum_price=Money.from_major_units("400"),
    )

    first = service.search(SearchSales(filters=filters, page_size=1))
    second = service.search(
        SearchSales(filters=filters, page_size=1, cursor=first.next_cursor)
    )

    assert first.has_more is True
    assert first.items[0].external_item_id == "1"
    assert second.has_more is False
    assert second.items[0].external_item_id == "4"


def test_top_level_search_records_normalized_recent_queries(
    sqlite_engine: Engine,
) -> None:
    seed_search_data(sqlite_engine)
    service = SearchSalesService(SqlAlchemyUnitOfWork.factory_for(sqlite_engine))

    service.search(SearchSales(query="  RTX   3070 "))
    service.search(SearchSales(query="RTX 3070"))
    recent = service.recent()

    assert len(recent) == 1
    assert recent[0].query == "RTX 3070"
    assert recent[0].use_count == 2
