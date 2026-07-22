"""Qt table model for lightweight completed-sale projections."""

from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from marktwert.application.search import SaleSearchResult
from marktwert.domain.money import Money


class SaleSearchTableModel(QAbstractTableModel):
    """Expose paginated local search results without widget-owned data."""

    HEADERS = (
        "Title",
        "Sold price",
        "Shipping",
        "Total",
        "Sold",
        "Condition",
        "Format",
    )

    def __init__(self) -> None:
        """Create an empty result model."""
        super().__init__()
        self._items: list[SaleSearchResult] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of loaded result rows."""
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the fixed projection column count."""
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        """Return display, alignment, or domain-row data."""
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return item
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in {1, 2, 3}:
            return int(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        return self._display_value(item, index.column())

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        """Return horizontal display headers."""
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def replace(self, items: tuple[SaleSearchResult, ...]) -> None:
        """Atomically replace all visible rows."""
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def append(self, items: tuple[SaleSearchResult, ...]) -> None:
        """Append one result page."""
        if not items:
            return
        first_row = len(self._items)
        last_row = first_row + len(items) - 1
        self.beginInsertRows(QModelIndex(), first_row, last_row)
        self._items.extend(items)
        self.endInsertRows()

    @staticmethod
    def _display_value(item: SaleSearchResult, column: int) -> str:
        values = (
            item.title,
            _format_money(item.sold_price),
            _format_money(item.shipping_price) if item.shipping_price else "—",
            _format_money(item.total_price),
            item.sold_at.astimezone().strftime("%d.%m.%Y"),
            item.condition.value.title() if item.condition else "—",
            item.listing_format.value.replace("_", " ").title()
            if item.listing_format
            else "—",
        )
        return values[column]


def _format_money(money: Money) -> str:
    amount = money.major_units.quantize(Decimal("0.01"))
    integer_part, decimal_part = f"{amount:.2f}".split(".")
    grouped = f"{int(integer_part):,}".replace(",", ".")
    return f"{grouped},{decimal_part} {money.currency}"
