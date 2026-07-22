"""Persistence port for accepted-sale analytical projections."""

from datetime import datetime
from typing import Protocol

from marktwert.application.analytics.models import SaleAnalyticsPoint
from marktwert.domain.sales import TrackedProductId


class MarketAnalyticsRepository(Protocol):
    """Load bounded accepted-sale projections."""

    def list_accepted(
        self,
        product_id: TrackedProductId,
        *,
        sold_from: datetime | None,
    ) -> tuple[SaleAnalyticsPoint, ...]:
        """Return accepted sales ordered chronologically."""
