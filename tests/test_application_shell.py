"""Smoke tests for the Qt application shell."""

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from marktwert import APPLICATION
from marktwert.bootstrap import create_application
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
