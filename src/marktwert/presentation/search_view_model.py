"""Asynchronous Qt view model for local completed-sales search."""

import logging
from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from marktwert.application.search import (
    RecentSearch,
    SaleSearchFilters,
    SaleSearchPage,
    SearchSales,
    SearchSalesService,
)
from marktwert.presentation.search_table_model import SaleSearchTableModel

LOGGER = logging.getLogger(__name__)
SHUTDOWN_WAIT_MILLISECONDS = 5_000


@dataclass(frozen=True, slots=True)
class _SearchPayload:
    page: SaleSearchPage
    recent: tuple[RecentSearch, ...] | None


class _WorkerSignals(QObject):
    succeeded = Signal(int, bool, object)
    failed = Signal(int, str)


class _SearchWorker(QRunnable):
    def __init__(
        self,
        *,
        generation: int,
        append: bool,
        service: SearchSalesService,
        request: SearchSales,
    ) -> None:
        super().__init__()
        self.signals = _WorkerSignals()
        self._generation = generation
        self._append = append
        self._service = service
        self._request = request

    @Slot()
    def run(self) -> None:
        """Execute database work outside the Qt UI thread."""
        try:
            page = self._service.search(self._request)
            recent = (
                self._service.recent()
                if self._request.cursor is None and self._request.query
                else None
            )
            self.signals.succeeded.emit(
                self._generation,
                self._append,
                _SearchPayload(page=page, recent=recent),
            )
        except Exception as error:
            LOGGER.exception("Local sale search failed")
            self.signals.failed.emit(self._generation, str(error))


class SaleSearchViewModel(QObject):
    """Coordinate asynchronous searches and presentation-ready table state."""

    loading_changed = Signal(bool)
    status_changed = Signal(str)
    has_more_changed = Signal(bool)
    recent_changed = Signal(object)

    def __init__(
        self,
        service: SearchSalesService,
        *,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        """Initialize search state and its bounded worker pool."""
        super().__init__()
        self.table_model = SaleSearchTableModel()
        self._service = service
        self._thread_pool = thread_pool or QThreadPool()
        self._thread_pool.setMaxThreadCount(1)
        self._generation = 0
        self._loading = False
        self._active_request: SearchSales | None = None
        self._next_cursor = None
        self._workers: set[_SearchWorker] = set()

    @property
    def is_loading(self) -> bool:
        """Return whether a current-generation query is running."""
        return self._loading

    @property
    def has_more(self) -> bool:
        """Return whether another result page is available."""
        return self._next_cursor is not None

    def search(
        self,
        query: str,
        *,
        filters: SaleSearchFilters | None = None,
    ) -> None:
        """Start a new search and supersede any stale result."""
        request = SearchSales(
            query=query,
            filters=filters or SaleSearchFilters(),
        )
        self._active_request = request
        self._next_cursor = None
        self.table_model.replace(())
        self.has_more_changed.emit(False)
        self._start(request, append=False)

    def load_more(self) -> None:
        """Load the next keyset page when available."""
        if self._loading or self._active_request is None or self._next_cursor is None:
            return
        self._start(
            replace(self._active_request, cursor=self._next_cursor),
            append=True,
        )

    def shutdown(self) -> None:
        """Discard queued work and wait briefly for the active query."""
        self._generation += 1
        self._thread_pool.clear()
        self._thread_pool.waitForDone(SHUTDOWN_WAIT_MILLISECONDS)
        self._workers.clear()

    def _start(self, request: SearchSales, *, append: bool) -> None:
        self._generation += 1
        generation = self._generation
        self._set_loading(True)
        self.status_changed.emit("Searching local sales…")
        worker = _SearchWorker(
            generation=generation,
            append=append,
            service=self._service,
            request=request,
        )
        self._workers.add(worker)
        worker.signals.succeeded.connect(self._on_succeeded)
        worker.signals.failed.connect(self._on_failed)
        worker.signals.succeeded.connect(lambda *_: self._workers.discard(worker))
        worker.signals.failed.connect(lambda *_: self._workers.discard(worker))
        self._thread_pool.start(worker)

    @Slot(int, bool, object)
    def _on_succeeded(
        self,
        generation: int,
        append: bool,
        raw_payload: object,
    ) -> None:
        if generation != self._generation:
            return
        payload = raw_payload
        if not isinstance(payload, _SearchPayload):
            self._on_failed(generation, "Search returned an invalid result")
            return
        if append:
            self.table_model.append(payload.page.items)
        else:
            self.table_model.replace(payload.page.items)
        self._next_cursor = payload.page.next_cursor
        self._set_loading(False)
        self.has_more_changed.emit(self.has_more)
        count = self.table_model.rowCount()
        self.status_changed.emit(
            f"{count} local sale{'s' if count != 1 else ''} loaded"
        )
        if payload.recent is not None:
            self.recent_changed.emit(payload.recent)

    @Slot(int, str)
    def _on_failed(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self._set_loading(False)
        self.status_changed.emit(message or "Local search failed")

    def _set_loading(self, loading: bool) -> None:
        if self._loading == loading:
            return
        self._loading = loading
        self.loading_changed.emit(loading)
