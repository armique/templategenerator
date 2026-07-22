"""Integration tests for asynchronous product and import operations."""

from pathlib import Path

from PySide6.QtWidgets import QListWidget
from pytestqt.qtbot import QtBot

from marktwert.application.imports import ImportCompletedSalesService, ImportPreview
from marktwert.application.products import TrackedProductService
from marktwert.domain.sales import CompletedSalesCriteria, TrackedProduct
from marktwert.infrastructure.imports import TabularSalesFileReaderFactory
from marktwert.infrastructure.persistence import (
    SqlAlchemyUnitOfWork,
    create_sqlite_engine,
    upgrade_database,
)
from marktwert.presentation.product_view_model import ProductWorkspaceViewModel
from marktwert.presentation.product_workspace import ProductWorkspaceDialog


def test_product_view_model_manages_product_and_import(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "workspace.db")
    upgrade_database(engine)
    factory = SqlAlchemyUnitOfWork.factory_for(engine)
    view_model = ProductWorkspaceViewModel(
        TrackedProductService(factory),
        ImportCompletedSalesService(factory, TabularSalesFileReaderFactory()),
    )
    product_snapshots: list[object] = []
    previews: list[object] = []
    reports: list[object] = []
    view_model.products_changed.connect(product_snapshots.append)
    view_model.preview_ready.connect(previews.append)
    view_model.import_finished.connect(reports.append)

    view_model.create_product(
        name="GPU",
        criteria=CompletedSalesCriteria(query="RTX 3070"),
    )
    qtbot.waitUntil(lambda: not view_model.is_busy)

    products = product_snapshots[-1]
    assert isinstance(products, tuple)
    assert len(products) == 1
    product = products[0]
    assert isinstance(product, TrackedProduct)

    source_file = tmp_path / "sales.csv"
    source_file.write_text(
        "item_id;title;sold_price;sold_at\n"
        "1;RTX 3070 Gaming OC;300,00;21.07.2026\n",
        encoding="utf-8",
    )
    view_model.preview_import(product.id, source_file)
    qtbot.waitUntil(lambda: not view_model.is_busy)

    assert isinstance(previews[-1], ImportPreview)
    assert len(previews[-1].rows) == 1

    view_model.import_file(product.id, source_file)
    qtbot.waitUntil(lambda: not view_model.is_busy)

    assert reports
    assert reports[-1].created_observations == 1

    dialog = ProductWorkspaceDialog(view_model)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not view_model.is_busy)
    product_list = dialog.findChild(QListWidget, "trackedProductList")
    assert product_list.count() == 1
    view_model.shutdown()
    engine.dispose()
