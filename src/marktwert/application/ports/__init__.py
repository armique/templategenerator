"""Abstract interfaces implemented by infrastructure adapters."""

from marktwert.application.ports.persistence import (
    ObservationUpsertResult,
    SaleObservationRepository,
    TrackedProductRepository,
    UnitOfWork,
    UnitOfWorkFactory,
)

__all__ = [
    "ObservationUpsertResult",
    "SaleObservationRepository",
    "TrackedProductRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
