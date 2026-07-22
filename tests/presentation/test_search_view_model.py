"""Tests for asynchronous local-search presentation models."""

from datetime import UTC, datetime

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QLineEdit, QPushButton, QTableView
from pytestqt.qtbot import QtBot

from marktwert.application.search import (
    RecentSearch,
    SaleSearchPage,
    SaleSearchResult,
    SearchCursor,
    SearchSales,
)
from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ClassificationDecision,
    ItemCondition,
    ListingFormat,
)
from marktwert.presentation.main_window import MainWindow
from marktwert.presentation.search_table_model import SaleSearchTableModel
from marktwert.presentation.search_view_model import SaleSearchViewModel

SOLD_AT = datetime(2026, 7, 20, 12, tzinfo=UTC)


def make_result(item_id: int) -> SaleSearchResult:
    """Create a lightweight result projection."""
    return SaleSearchResult(
        observation_id=item_id,
        external_item_id=str(item_id),
        title=f"RTX 3070 result {item_id}",
        sold_price=Money.from_major_units("300"),
        shipping_price=Money.from_major_units("6.99"),
        sold_at=SOLD_AT,
        condition=ItemCondition.USED,
        listing_format=ListingFormat.BUY_IT_NOW,
        classification=ClassificationDecision.ACCEPT,
    )


class FakeSearchService:
    """Return deterministic pages for view-model tests."""

    def search(self, request: SearchSales) -> SaleSearchPage:
        """Return a first or second page based on the cursor."""
        if request.cursor is None:
            return SaleSearchPage(
                items=(make_result(1),),
                next_cursor=SearchCursor(SOLD_AT, 1),
            )
        return SaleSearchPage(items=(make_result(2),), next_cursor=None)

    def recent(self, *, limit: int = 10) -> tuple[RecentSearch, ...]:
        """Return one recent query."""
        del limit
        return (RecentSearch("RTX 3070", SOLD_AT, 1),)


def test_table_model_formats_exact_money_and_rows() -> None:
    model = SaleSearchTableModel()
    model.replace((make_result(1),))

    assert model.rowCount() == 1
    assert model.columnCount() == 7
    assert model.data(model.index(0, 0)) == "RTX 3070 result 1"
    assert model.data(model.index(0, 3)) == "306,99 EUR"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole) == make_result(1)
    assert model.rowCount(QModelIndex()) == 1


def test_view_model_searches_and_loads_next_page(qtbot: QtBot) -> None:
    view_model = SaleSearchViewModel(FakeSearchService())  # type: ignore[arg-type]
    statuses: list[str] = []
    recent: list[object] = []
    view_model.status_changed.connect(statuses.append)
    view_model.recent_changed.connect(recent.append)

    view_model.search("RTX 3070")
    qtbot.waitUntil(lambda: not view_model.is_loading)

    assert view_model.table_model.rowCount() == 1
    assert view_model.has_more is True
    assert recent

    view_model.load_more()
    qtbot.waitUntil(lambda: not view_model.is_loading)

    assert view_model.table_model.rowCount() == 2
    assert view_model.has_more is False
    assert statuses[-1] == "2 local sales loaded"
    view_model.shutdown()


def test_main_window_executes_functional_local_search(qtbot: QtBot) -> None:
    view_model = SaleSearchViewModel(FakeSearchService())  # type: ignore[arg-type]
    window = MainWindow(view_model)
    qtbot.addWidget(window)
    window.show()
    search_input = window.findChild(QLineEdit, "searchInput")
    search_button = window.findChild(QPushButton, "searchButton")
    table = window.findChild(QTableView, "salesTable")

    search_input.setText("RTX 3070")
    qtbot.mouseClick(search_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not view_model.is_loading)

    assert table.isVisible()
    assert table.model().rowCount() == 1
    view_model.shutdown()
