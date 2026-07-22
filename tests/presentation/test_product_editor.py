"""Tests for tracked-product criteria editing."""

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QLineEdit
from pytestqt.qtbot import QtBot

from marktwert.domain.money import Money
from marktwert.domain.sales import CompletedSalesCriteria, TrackedProduct
from marktwert.presentation.product_editor import TrackedProductEditor


def test_editor_builds_valid_collection_criteria(qtbot: QtBot) -> None:
    editor = TrackedProductEditor()
    qtbot.addWidget(editor)
    editor.findChild(QLineEdit, "productName").setText("Primary GPU")
    editor.findChild(QLineEdit, "productQuery").setText("RTX 3070")
    maximum_enabled = editor.findChild(QCheckBox, "maximumPriceEnabled")
    maximum_price = editor.findChild(QDoubleSpinBox, "maximumPrice")
    maximum_enabled.setChecked(True)
    maximum_price.setValue(350.50)

    data = editor.form_data()

    assert data.name == "Primary GPU"
    assert data.criteria.query == "RTX 3070"
    assert data.criteria.maximum_price == Money.from_major_units("350.50")
    assert data.criteria.lookback_days == 30
    assert data.criteria.standalone_working_only is True


def test_editor_populates_existing_product(qtbot: QtBot) -> None:
    product = TrackedProduct.create(
        "CPU",
        CompletedSalesCriteria(
            query="Ryzen 5700X",
            maximum_price=Money.from_major_units("180"),
        ),
    ).set_enabled(enabled=False)
    editor = TrackedProductEditor(product)
    qtbot.addWidget(editor)

    data = editor.form_data()

    assert data.name == "CPU"
    assert data.criteria == product.criteria
    assert data.enabled is False
