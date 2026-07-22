"""Integration tests for SQLAlchemy repositories and transactions."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from marktwert.domain.money import Money
from marktwert.domain.sales import (
    CompletedSalesCriteria,
    ItemCondition,
    ListingFormat,
    ProductSnapshot,
    SaleObservation,
    SellerSnapshot,
    TrackedProduct,
)
from marktwert.infrastructure.persistence.models import (
    SaleObservationRow,
    SourceRevisionRow,
    TrackedProductSaleRow,
)
from marktwert.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

SOLD_AT = datetime(2026, 7, 1, 12, tzinfo=UTC)
FIRST_ACQUISITION = datetime(2026, 7, 2, 8, tzinfo=UTC)


def make_product(name: str = "RTX 3070") -> TrackedProduct:
    """Create a representative tracked product."""
    return TrackedProduct.create(
        name=name,
        criteria=CompletedSalesCriteria(
            query="RTX 3070",
            maximum_price=Money.from_major_units("450"),
            required_title_terms=("8 GB",),
            additional_exclusion_terms=("water block",),
        ),
    )


def make_observation(**overrides: object) -> SaleObservation:
    """Create a representative completed-sale observation."""
    values: dict[str, object] = {
        "source": "ebay_de",
        "external_item_id": "item-123",
        "title": "Gigabyte RTX 3070 Gaming OC 8 GB",
        "sold_price": Money.from_major_units("300"),
        "sold_at": SOLD_AT,
        "acquired_at": FIRST_ACQUISITION,
        "raw_record_hash": "sha256:first",
        "condition": ItemCondition.USED,
        "listing_format": ListingFormat.BUY_IT_NOW,
    }
    values.update(overrides)
    return SaleObservation(**values)  # type: ignore[arg-type]


def test_tracked_product_round_trip_update_and_remove(
    sqlite_engine: Engine,
) -> None:
    factory = SqlAlchemyUnitOfWork.factory_for(sqlite_engine)
    product = make_product()

    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(product)
        unit_of_work.commit()

    edited = product.edit(name="Primary GPU").set_enabled(enabled=False)
    with factory() as unit_of_work:
        loaded = unit_of_work.tracked_products.get(product.id)
        unit_of_work.tracked_products.save(edited)
        unit_of_work.commit()

    assert loaded == product
    with factory() as unit_of_work:
        assert unit_of_work.tracked_products.list_all() == (edited,)
        assert unit_of_work.tracked_products.remove(product.id) is True
        assert unit_of_work.tracked_products.remove(product.id) is False
        unit_of_work.commit()

    with factory() as unit_of_work:
        assert unit_of_work.tracked_products.get(product.id) is None


def test_uncommitted_unit_of_work_rolls_back(sqlite_engine: Engine) -> None:
    factory = SqlAlchemyUnitOfWork.factory_for(sqlite_engine)
    product = make_product()

    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(product)

    with factory() as unit_of_work:
        assert unit_of_work.tracked_products.get(product.id) is None


def test_observation_upsert_is_idempotent_and_enriches_missing_fields(
    sqlite_engine: Engine,
) -> None:
    factory = SqlAlchemyUnitOfWork.factory_for(sqlite_engine)
    product = make_product()
    original = make_observation()

    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(product)
        first_result = unit_of_work.sale_observations.upsert(
            original,
            matched_product_id=product.id,
        )
        unit_of_work.commit()

    assert first_result.created is True
    assert first_result.source_revision_added is True
    assert first_result.product_link_added is True

    with factory() as unit_of_work:
        duplicate_result = unit_of_work.sale_observations.upsert(
            original,
            matched_product_id=product.id,
        )
        unit_of_work.commit()

    assert duplicate_result.created is False
    assert duplicate_result.enriched_fields == ()
    assert duplicate_result.source_revision_added is False
    assert duplicate_result.product_link_added is False

    enriched = make_observation(
        shipping_price=Money.from_major_units("7.49"),
        listing_url="https://www.ebay.de/itm/item-123",
        location="Berlin",
        seller=SellerSnapshot(
            name="hardware-shop",
            feedback_percentage=Decimal("99.80"),
            feedback_count=1200,
        ),
        product=ProductSnapshot(
            normalized_title="Gigabyte RTX 3070 Gaming OC",
            brand="Gigabyte",
            model="RTX 3070",
            category="gpu",
            revision="Rev 2",
            memory_size_gb=8,
            normalization_confidence=9000,
            normalization_version="hardware-rules-1",
            normalization_evidence=("model:RTX 3070:pattern",),
        ),
        acquired_at=datetime(2026, 7, 16, 8, tzinfo=UTC),
        raw_record_hash="sha256:enriched",
    )
    with factory() as unit_of_work:
        enriched_result = unit_of_work.sale_observations.upsert(
            enriched,
            matched_product_id=product.id,
        )
        unit_of_work.commit()

    assert enriched_result.created is False
    assert set(enriched_result.enriched_fields) == {
        "shipping_price",
        "listing_url",
        "location",
        "seller",
        "product",
    }
    assert enriched_result.source_revision_added is True

    with factory() as unit_of_work:
        stored = unit_of_work.sale_observations.get("ebay_de", "item-123")
        listed = unit_of_work.sale_observations.list_for_product(product.id)

    assert stored is not None
    assert stored.shipping_price == Money.from_major_units("7.49")
    assert stored.acquired_at == FIRST_ACQUISITION
    assert stored.seller.name == "hardware-shop"
    assert stored.product.normalized_title == "Gigabyte RTX 3070 Gaming OC"
    assert stored.product.memory_size_gb == 8
    assert stored.product.normalization_evidence == ("model:RTX 3070:pattern",)
    assert listed == (stored,)

    with Session(sqlite_engine) as session:
        observation_count = session.scalar(
            select(func.count()).select_from(SaleObservationRow)
        )
        revision_count = session.scalar(
            select(func.count()).select_from(SourceRevisionRow)
        )
        link_count = session.scalar(
            select(func.count()).select_from(TrackedProductSaleRow)
        )

    assert observation_count == 1
    assert revision_count == 2
    assert link_count == 1


def test_one_observation_can_match_multiple_products(sqlite_engine: Engine) -> None:
    factory = SqlAlchemyUnitOfWork.factory_for(sqlite_engine)
    first_product = make_product("RTX 3070")
    second_product = make_product("Gigabyte GPUs")
    observation = make_observation()

    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(first_product)
        unit_of_work.tracked_products.save(second_product)
        unit_of_work.sale_observations.upsert(
            observation,
            matched_product_id=first_product.id,
        )
        second_result = unit_of_work.sale_observations.upsert(
            observation,
            matched_product_id=second_product.id,
        )
        unit_of_work.commit()

    assert second_result.created is False
    assert second_result.product_link_added is True
    with factory() as unit_of_work:
        assert unit_of_work.sale_observations.list_for_product(
            first_product.id
        ) == (observation,)
        assert unit_of_work.sale_observations.list_for_product(
            second_product.id
        ) == (observation,)
