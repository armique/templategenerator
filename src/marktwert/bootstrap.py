"""Application composition root."""

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
from sqlalchemy import Engine

from marktwert import APPLICATION
from marktwert.application.analytics import MarketAnalyticsService
from marktwert.application.imports import ImportCompletedSalesService
from marktwert.application.products import TrackedProductService
from marktwert.application.search import SearchSalesService
from marktwert.infrastructure.imports import TabularSalesFileReaderFactory
from marktwert.infrastructure.persistence import (
    SqlAlchemyUnitOfWork,
    create_sqlite_engine,
    upgrade_database,
)
from marktwert.infrastructure.platform_paths import default_data_directory
from marktwert.presentation.main_window import MainWindow
from marktwert.presentation.analytics_view_model import AnalyticsViewModel
from marktwert.presentation.product_view_model import ProductWorkspaceViewModel
from marktwert.presentation.search_view_model import SaleSearchViewModel
from marktwert.presentation.theme import DARK_STYLESHEET


@dataclass(frozen=True, slots=True)
class ApplicationRuntime:
    """Own process-lifetime application services and resources."""

    engine: Engine
    view_model: SaleSearchViewModel
    product_view_model: ProductWorkspaceViewModel
    analytics_view_model: AnalyticsViewModel
    window: MainWindow

    def shutdown(self) -> None:
        """Stop background work before releasing database connections."""
        self.view_model.shutdown()
        self.product_view_model.shutdown()
        self.analytics_view_model.shutdown()
        self.engine.dispose()


def create_application(arguments: Sequence[str] | None = None) -> QApplication:
    """Create and configure the sole Qt application instance."""
    existing = QApplication.instance()
    if existing is None:
        app = QApplication(list(arguments) if arguments is not None else sys.argv)
    elif isinstance(existing, QApplication):
        app = existing
    else:
        message = "A non-GUI QCoreApplication already exists"
        raise RuntimeError(message)

    QCoreApplication.setApplicationName(APPLICATION.name)
    QCoreApplication.setApplicationVersion(APPLICATION.version)
    QCoreApplication.setOrganizationName(APPLICATION.organization)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    return app


def create_runtime(database_path: Path | None = None) -> ApplicationRuntime:
    """Compose the local database, search service, view model, and window."""
    resolved_database_path = (
        database_path
        if database_path is not None
        else default_data_directory() / "marktwert.db"
    )
    engine = create_sqlite_engine(resolved_database_path)
    upgrade_database(engine)
    unit_of_work_factory = SqlAlchemyUnitOfWork.factory_for(engine)
    view_model = SaleSearchViewModel(SearchSalesService(unit_of_work_factory))
    product_view_model = ProductWorkspaceViewModel(
        TrackedProductService(unit_of_work_factory),
        ImportCompletedSalesService(
            unit_of_work_factory,
            TabularSalesFileReaderFactory(),
        ),
    )
    analytics_view_model = AnalyticsViewModel(
        MarketAnalyticsService(unit_of_work_factory),
        TrackedProductService(unit_of_work_factory),
    )
    return ApplicationRuntime(
        engine=engine,
        view_model=view_model,
        product_view_model=product_view_model,
        analytics_view_model=analytics_view_model,
        window=MainWindow(view_model, product_view_model, analytics_view_model),
    )


def run(arguments: Sequence[str] | None = None) -> int:
    """Compose, display, and execute the desktop application."""
    app = create_application(arguments)
    runtime = create_runtime()
    runtime.window.show()
    try:
        return app.exec()
    finally:
        runtime.shutdown()
