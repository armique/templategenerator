"""Asynchronous view model for tracked products and file imports."""

import logging
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from marktwert.application.imports import (
    ImportCompletedSalesService,
    ImportPreview,
    ImportReport,
    ImportSalesFile,
)
from marktwert.application.products import TrackedProductService
from marktwert.domain.sales import (
    CompletedSalesCriteria,
    TrackedProduct,
    TrackedProductId,
)

LOGGER = logging.getLogger(__name__)
SHUTDOWN_WAIT_MILLISECONDS = 5_000


class _Operation(StrEnum):
    PRODUCTS = "products"
    PREVIEW = "preview"
    IMPORT = "import"


class _WorkerSignals(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str)


class _OperationWorker(QRunnable):
    def __init__(self, operation: _Operation, action: Callable[[], object]) -> None:
        super().__init__()
        self.signals = _WorkerSignals()
        self._operation = operation
        self._action = action

    @Slot()
    def run(self) -> None:
        """Execute one application operation outside the UI thread."""
        try:
            self.signals.succeeded.emit(self._operation.value, self._action())
        except Exception as error:
            LOGGER.exception("Product workspace operation failed")
            self.signals.failed.emit(self._operation.value, str(error))


class ProductWorkspaceViewModel(QObject):
    """Coordinate tracked-product CRUD, previews, and imports."""

    busy_changed = Signal(bool)
    status_changed = Signal(str)
    products_changed = Signal(object)
    preview_ready = Signal(object)
    import_finished = Signal(object)
    error_raised = Signal(str)

    def __init__(
        self,
        product_service: TrackedProductService,
        import_service: ImportCompletedSalesService,
        *,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        """Initialize services and a serialized background worker pool."""
        super().__init__()
        self._product_service = product_service
        self._import_service = import_service
        self._thread_pool = thread_pool or QThreadPool()
        self._thread_pool.setMaxThreadCount(1)
        self._busy = False
        self._workers: set[_OperationWorker] = set()

    @property
    def is_busy(self) -> bool:
        """Return whether an operation is currently running."""
        return self._busy

    def refresh_products(self) -> None:
        """Load the current tracked-product collection."""
        self._start(
            _Operation.PRODUCTS,
            self._product_service.list_all,
            status="Loading tracked products…",
        )

    def create_product(
        self,
        *,
        name: str,
        criteria: CompletedSalesCriteria,
    ) -> None:
        """Create a product and refresh the collection."""

        def action() -> tuple[TrackedProduct, ...]:
            self._product_service.create(name=name, criteria=criteria)
            return self._product_service.list_all()

        self._start(_Operation.PRODUCTS, action, status="Creating product…")

    def update_product(
        self,
        product: TrackedProduct,
        *,
        name: str,
        criteria: CompletedSalesCriteria,
        enabled: bool,
    ) -> None:
        """Update a product and refresh the collection."""

        def action() -> tuple[TrackedProduct, ...]:
            self._product_service.update(
                product.id,
                name=name,
                criteria=criteria,
                enabled=enabled,
            )
            return self._product_service.list_all()

        self._start(_Operation.PRODUCTS, action, status="Updating product…")

    def remove_product(self, product_id: TrackedProductId) -> None:
        """Remove a product and refresh the collection."""

        def action() -> tuple[TrackedProduct, ...]:
            self._product_service.remove(product_id)
            return self._product_service.list_all()

        self._start(_Operation.PRODUCTS, action, status="Removing product…")

    def preview_import(self, product_id: TrackedProductId, path: Path) -> None:
        """Preview a completed-sales file without writing rows."""
        command = ImportSalesFile(
            path=path,
            source="manual_file",
            tracked_product_id=product_id,
        )
        self._start(
            _Operation.PREVIEW,
            lambda: self._import_service.preview(command),
            status="Validating import preview…",
        )

    def import_file(self, product_id: TrackedProductId, path: Path) -> None:
        """Import a validated completed-sales file."""
        command = ImportSalesFile(
            path=path,
            source="manual_file",
            tracked_product_id=product_id,
        )
        self._start(
            _Operation.IMPORT,
            lambda: self._import_service.execute(command),
            status="Importing completed sales…",
        )

    def shutdown(self) -> None:
        """Discard queued work and wait briefly for an active operation."""
        self._thread_pool.clear()
        self._thread_pool.waitForDone(SHUTDOWN_WAIT_MILLISECONDS)
        self._workers.clear()

    def _start(
        self,
        operation: _Operation,
        action: Callable[[], object],
        *,
        status: str,
    ) -> None:
        if self._busy:
            self.status_changed.emit("Wait for the current operation to finish.")
            return
        self._set_busy(True)
        self.status_changed.emit(status)
        worker = _OperationWorker(operation, action)
        self._workers.add(worker)
        worker.signals.succeeded.connect(self._on_succeeded)
        worker.signals.failed.connect(self._on_failed)
        worker.signals.succeeded.connect(lambda *_: self._workers.discard(worker))
        worker.signals.failed.connect(lambda *_: self._workers.discard(worker))
        self._thread_pool.start(worker)

    @Slot(str, object)
    def _on_succeeded(self, raw_operation: str, result: object) -> None:
        self._set_busy(False)
        operation = _Operation(raw_operation)
        if operation is _Operation.PRODUCTS and isinstance(result, tuple):
            self.products_changed.emit(result)
            self.status_changed.emit(f"{len(result)} tracked products")
        elif operation is _Operation.PREVIEW and isinstance(result, ImportPreview):
            self.preview_ready.emit(result)
            self.status_changed.emit(f"{len(result.rows)} preview rows validated")
        elif operation is _Operation.IMPORT and isinstance(result, ImportReport):
            self.import_finished.emit(result)
            self.status_changed.emit(
                f"{result.stored_rows} valid rows processed; "
                f"{result.invalid_rows} invalid"
            )
        else:
            self.error_raised.emit("Operation returned an invalid result.")

    @Slot(str, str)
    def _on_failed(self, raw_operation: str, message: str) -> None:
        del raw_operation
        self._set_busy(False)
        safe_message = message or "Product operation failed"
        self.error_raised.emit(safe_message)
        self.status_changed.emit(safe_message)

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)
