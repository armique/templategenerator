"""Tracked-product management use cases."""

from marktwert.application.ports import UnitOfWorkFactory
from marktwert.domain.sales import (
    CompletedSalesCriteria,
    TrackedProduct,
    TrackedProductId,
)


class TrackedProductNotFoundError(LookupError):
    """Report that a requested tracked product no longer exists."""


class TrackedProductService:
    """Create, edit, list, enable, and remove tracked products."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        """Initialize the service with transaction creation."""
        self._unit_of_work_factory = unit_of_work_factory

    def list_all(self) -> tuple[TrackedProduct, ...]:
        """Return all tracked products in display order."""
        with self._unit_of_work_factory() as unit_of_work:
            return tuple(unit_of_work.tracked_products.list_all())

    def create(
        self,
        *,
        name: str,
        criteria: CompletedSalesCriteria,
    ) -> TrackedProduct:
        """Create and persist a new enabled tracked product."""
        product = TrackedProduct.create(name=name, criteria=criteria)
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.tracked_products.save(product)
            unit_of_work.commit()
        return product

    def update(
        self,
        product_id: TrackedProductId,
        *,
        name: str,
        criteria: CompletedSalesCriteria,
        enabled: bool,
    ) -> TrackedProduct:
        """Update a tracked product while preserving its identity."""
        with self._unit_of_work_factory() as unit_of_work:
            current = unit_of_work.tracked_products.get(product_id)
            if current is None:
                raise TrackedProductNotFoundError(str(product_id.value))
            updated = current.edit(name=name, criteria=criteria).set_enabled(
                enabled=enabled
            )
            unit_of_work.tracked_products.save(updated)
            unit_of_work.commit()
        return updated

    def remove(self, product_id: TrackedProductId) -> None:
        """Remove a tracked product or report a stale request."""
        with self._unit_of_work_factory() as unit_of_work:
            if not unit_of_work.tracked_products.remove(product_id):
                raise TrackedProductNotFoundError(str(product_id.value))
            unit_of_work.commit()
