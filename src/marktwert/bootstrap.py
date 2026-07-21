"""Application composition root."""

import sys
from collections.abc import Sequence

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from marktwert import APPLICATION
from marktwert.presentation.main_window import MainWindow
from marktwert.presentation.theme import DARK_STYLESHEET


def create_application(arguments: Sequence[str] | None = None) -> QApplication:
    """Create and configure the sole Qt application instance."""
    existing = QApplication.instance()
    if existing is not None:
        return existing

    app = QApplication(list(arguments) if arguments is not None else sys.argv)
    QCoreApplication.setApplicationName(APPLICATION.name)
    QCoreApplication.setApplicationVersion(APPLICATION.version)
    QCoreApplication.setOrganizationName(APPLICATION.organization)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    return app


def run(arguments: Sequence[str] | None = None) -> int:
    """Compose, display, and execute the desktop application."""
    app = create_application(arguments)
    window = MainWindow()
    window.show()
    return app.exec()
