"""Local completed-sales search use cases."""

from marktwert.application.ports import UnitOfWorkFactory
from marktwert.application.search.models import RecentSearch, SaleSearchPage, SearchSales


class SearchSalesService:
    """Execute local searches and maintain query history transactionally."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        """Initialize the service with a unit-of-work factory."""
        self._unit_of_work_factory = unit_of_work_factory

    def search(self, request: SearchSales) -> SaleSearchPage:
        """Return one result page and record a new top-level query."""
        with self._unit_of_work_factory() as unit_of_work:
            page = unit_of_work.sale_search.search(request)
            if request.query and request.cursor is None:
                unit_of_work.sale_search.record_recent(request.query)
                unit_of_work.commit()
            return page

    def recent(self, *, limit: int = 10) -> tuple[RecentSearch, ...]:
        """Return recent searches without opening a write transaction."""
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.sale_search.list_recent(limit=limit)
