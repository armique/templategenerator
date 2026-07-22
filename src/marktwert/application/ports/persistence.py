"""Persistence contracts required by application use cases."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Self

from marktwert.domain.sales import (
    ClassificationDecision,
    ClassificationResult,
    SaleObservation,
    TrackedProduct,
    TrackedProductId,
)

if TYPE_CHECKING:
    from marktwert.application.analytics.ports import MarketAnalyticsRepository
    from marktwert.application.search.ports import SaleSearchRepository

ACCEPTED_CLASSIFICATION = ClassificationResult(ClassificationDecision.ACCEPT)


@dataclass(frozen=True, slots=True)
class ObservationUpsertResult:
    """Describe all durable effects of an idempotent observation upsert."""

    created: bool
    enriched_fields: tuple[str, ...] = ()
    source_revision_added: bool = False
    product_link_added: bool = False
    classification_updated: bool = False


class TrackedProductRepository(Protocol):
    """Persist user-managed completed-sale collection profiles."""

    def save(self, product: TrackedProduct) -> None:
        """Insert or update a tracked product."""

    def get(self, product_id: TrackedProductId) -> TrackedProduct | None:
        """Return a tracked product by identity."""

    def list_all(self) -> Sequence[TrackedProduct]:
        """Return every tracked product in display order."""

    def remove(self, product_id: TrackedProductId) -> bool:
        """Remove a tracked product and report whether it existed."""


class SaleObservationRepository(Protocol):
    """Persist normalized completed-sale observations without duplicates."""

    def upsert(
        self,
        observation: SaleObservation,
        *,
        matched_product_id: TrackedProductId,
        classification: ClassificationResult = ACCEPTED_CLASSIFICATION,
    ) -> ObservationUpsertResult:
        """Insert, enrich, and associate one source observation."""

    def get(
        self,
        source: str,
        external_item_id: str,
    ) -> SaleObservation | None:
        """Return one observation by its stable source identity."""

    def list_for_product(
        self,
        product_id: TrackedProductId,
    ) -> Sequence[SaleObservation]:
        """Return observations associated with a tracked product."""


class UnitOfWork(AbstractContextManager["UnitOfWork"], Protocol):
    """Own a database transaction and its repositories."""

    tracked_products: TrackedProductRepository
    sale_observations: SaleObservationRepository
    sale_search: SaleSearchRepository
    market_analytics: MarketAnalyticsRepository

    def __enter__(self) -> Self:
        """Open the transaction scope."""

    def commit(self) -> None:
        """Commit all changes in the transaction."""

    def rollback(self) -> None:
        """Roll back all changes in the transaction."""


class UnitOfWorkFactory(Protocol):
    """Create independent persistence transaction scopes."""

    def __call__(self) -> UnitOfWork:
        """Create a unit of work."""
