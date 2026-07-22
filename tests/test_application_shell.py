"""Smoke tests for the Qt application shell."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton
from pytestqt.qtbot import QtBot

from marktwert import APPLICATION
from marktwert.bootstrap import create_application, create_runtime
from marktwert.presentation.main_window import MainWindow


def test_bootstrap_configures_application_identity(
    qapp: QApplication,
) -> None:
    app = create_application([])

    assert app is qapp
    assert QCoreApplication.applicationName() == APPLICATION.name
    assert QCoreApplication.applicationVersion() == APPLICATION.version
    assert QCoreApplication.organizationName() == APPLICATION.organization


def test_main_window_has_safe_foundation_state(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == APPLICATION.name
    assert window.minimumWidth() == 960
    assert "No data source configured" in window.statusBar().currentMessage()


def test_runtime_composes_searchable_local_database(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    runtime = create_runtime(tmp_path / "runtime.db")
    qtbot.addWidget(runtime.window)

    assert runtime.window.findChild(QLineEdit, "searchInput").isEnabled()
    assert runtime.window.findChild(
        QPushButton,
        "manageProductsButton",
    ).isEnabled()
    assert runtime.window.findChild(
        QPushButton,
        "marketAnalysisButton",
    ).isEnabled()
    assert (tmp_path / "runtime.db").exists()
    runtime.shutdown()
