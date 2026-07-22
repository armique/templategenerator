"""Asynchronous view model for market analysis."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from marktwert.application.analytics import (
    AnalysisWindow,
    AnalyzeMarket,
    MarketAnalysis,
    MarketAnalyticsService,
)
from marktwert.application.products import TrackedProductService
from marktwert.domain.sales import TrackedProductId

LOGGER = logging.getLogger(__name__)
SHUTDOWN_WAIT_MILLISECONDS = 5_000


class _Signals(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str)


class _Worker(QRunnable):
    def __init__(self, operation: str, action: Callable[[], object]) -> None:
        super().__init__()
        self.signals = _Signals()
        self._operation = operation
        self._action = action

    @Slot()
    def run(self) -> None:
        """Execute analysis work outside the UI thread."""
        try:
            self.signals.succeeded.emit(self._operation, self._action())
        except Exception as error:
            LOGGER.exception("Market analysis failed")
            self.signals.failed.emit(str(error))


class AnalyticsViewModel(QObject):
    """Load products and calculate market analysis asynchronously."""

    busy_changed = Signal(bool)
    products_changed = Signal(object)
    analysis_ready = Signal(object)
    error_raised = Signal(str)

    def __init__(
        self,
        analytics_service: MarketAnalyticsService,
        product_service: TrackedProductService,
    ) -> None:
        """Initialize services and a serialized worker pool."""
        super().__init__()
        self._analytics_service = analytics_service
        self._product_service = product_service
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(1)
        self._busy = False
        self._workers: set[_Worker] = set()

    @property
    def is_busy(self) -> bool:
        """Return whether an analysis operation is active."""
        return self._busy

    def load_products(self) -> None:
        """Load selectable tracked products."""
        self._start("products", self._product_service.list_all)

    def analyze(
        self,
        product_id: TrackedProductId,
        window: AnalysisWindow,
        *,
        include_shipping: bool,
    ) -> None:
        """Calculate one requested market analysis."""
        request = AnalyzeMarket(product_id, window, include_shipping)
        self._start("analysis", lambda: self._analytics_service.analyze(request))

    def shutdown(self) -> None:
        """Wait briefly for active analysis before shutdown."""
        self._pool.clear()
        self._pool.waitForDone(SHUTDOWN_WAIT_MILLISECONDS)
        self._workers.clear()

    def _start(self, operation: str, action: Callable[[], object]) -> None:
        if self._busy:
            return
        self._busy = True
        self.busy_changed.emit(True)
        worker = _Worker(operation, action)
        self._workers.add(worker)
        worker.signals.succeeded.connect(self._on_succeeded)
        worker.signals.failed.connect(self._on_failed)
        worker.signals.succeeded.connect(lambda *_: self._workers.discard(worker))
        worker.signals.failed.connect(lambda *_: self._workers.discard(worker))
        self._pool.start(worker)

    @Slot(str, object)
    def _on_succeeded(self, operation: str, result: object) -> None:
        self._busy = False
        self.busy_changed.emit(False)
        if operation == "products" and isinstance(result, tuple):
            self.products_changed.emit(result)
        elif operation == "analysis" and isinstance(result, MarketAnalysis):
            self.analysis_ready.emit(result)
        else:
            self.error_raised.emit("Analysis returned an invalid result.")

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._busy = False
        self.busy_changed.emit(False)
        self.error_raised.emit(message or "Market analysis failed")
