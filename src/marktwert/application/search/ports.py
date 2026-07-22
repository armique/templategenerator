"""Persistence port for the local completed-sales workspace."""

from typing import Protocol

from marktwert.application.search.models import (
    RecentSearch,
    SaleSearchPage,
    SearchSales,
)


class SaleSearchRepository(Protocol):
    """Search lightweight local projections and maintain recent queries."""

    def search(self, request: SearchSales) -> SaleSearchPage:
        """Return one keyset-paginated result page."""

    def record_recent(self, query: str) -> None:
        """Record a successful non-empty query."""

    def list_recent(self, *, limit: int = 10) -> tuple[RecentSearch, ...]:
        """Return most recently used local queries."""
