"""Integration tests for tracked-product management use cases."""

from pathlib import Path

import pytest

from marktwert.application.products import (
    TrackedProductNotFoundError,
    TrackedProductService,
)
from marktwert.domain.money import Money
from marktwert.domain.sales import CompletedSalesCriteria
from marktwert.infrastructure.persistence import (
    SqlAlchemyUnitOfWork,
    create_sqlite_engine,
    upgrade_database,
)


def test_product_service_creates_updates_lists_and_removes(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "products.db")
    upgrade_database(engine)
    service = TrackedProductService(SqlAlchemyUnitOfWork.factory_for(engine))

    created = service.create(
        name="Graphics card",
        criteria=CompletedSalesCriteria(
            query="RTX 3070",
            maximum_price=Money.from_major_units("400"),
        ),
    )
    updated = service.update(
        created.id,
        name="Primary GPU",
        criteria=CompletedSalesCriteria(query="RTX 3070 8GB"),
        enabled=False,
    )

    assert updated.id == created.id
    assert updated.enabled is False
    assert service.list_all() == (updated,)

    service.remove(created.id)
    assert service.list_all() == ()
    with pytest.raises(TrackedProductNotFoundError):
        service.remove(created.id)
    engine.dispose()
