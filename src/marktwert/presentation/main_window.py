"""Main application window."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from marktwert import APPLICATION
from marktwert.application.search import RecentSearch
from marktwert.presentation.search_view_model import SaleSearchViewModel


class MainWindow(QMainWindow):
    """Display the responsive local-sales workspace."""

    def __init__(self, view_model: SaleSearchViewModel | None = None) -> None:
        """Initialize the main window and optional functional workspace."""
        super().__init__()
        self._view_model = view_model
        self.setWindowTitle(APPLICATION.name)
        self.setMinimumSize(960, 640)
        self.resize(1280, 800)
        self.setCentralWidget(self._build_content())
        self._connect_view_model()
        if view_model is None:
            self.statusBar().showMessage("Foundation ready · No data source configured")
        else:
            self.statusBar().showMessage("Local database ready")

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_workspace(), stretch=1)
        return content

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(8)

        brand = QLabel(APPLICATION.name)
        brand.setObjectName("brand")
        subtitle = QLabel("MARKET INTELLIGENCE")
        subtitle.setObjectName("eyebrow")
        self._recent_list = QListWidget()
        self._recent_list.setObjectName("recentSearches")
        self._recent_list.setMaximumHeight(150)
        self._recent_list.setVisible(False)

        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(32)
        layout.addWidget(self._navigation_label("OVERVIEW"))
        layout.addWidget(self._muted_label("Search"))
        layout.addWidget(self._muted_label("Favorites"))
        layout.addWidget(self._muted_label("Watchlists"))
        layout.addSpacing(24)
        layout.addWidget(self._navigation_label("RECENT SEARCHES"))
        layout.addWidget(self._recent_list)
        layout.addStretch()
        layout.addWidget(self._muted_label(f"Version {APPLICATION.version}"))
        return sidebar

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(48, 38, 48, 32)
        layout.setSpacing(22)

        eyebrow = QLabel("LOCAL SALES · COMPUTER HARDWARE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Completed-sales search")
        title.setObjectName("pageTitle")
        self._result_table = self._build_result_table()
        self._empty_state = self._build_empty_state()
        self._load_more_button = QPushButton("Load more")
        self._load_more_button.setVisible(False)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addLayout(self._build_search())
        layout.addWidget(self._empty_state, stretch=1)
        layout.addWidget(self._result_table, stretch=1)
        layout.addWidget(
            self._load_more_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        return workspace

    def _build_search(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText("Search, for example RTX 3070")
        self._search_input.setAccessibleName("Product search")
        self._search_input.setDisabled(self._view_model is None)
        self._search_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._search_button = QPushButton("Search")
        self._search_button.setObjectName("searchButton")
        self._search_button.setAccessibleName("Search completed sales")
        self._search_button.setDisabled(self._view_model is None)

        layout.addWidget(self._search_input, stretch=1)
        layout.addWidget(self._search_button)
        return layout

    def _build_result_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("salesTable")
        table.setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        if self._view_model is not None:
            table.setModel(self._view_model.table_model)
        return table

    def _build_empty_state(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("emptyState")

        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(10)

        self._empty_title = QLabel(
            "Search imported completed sales"
            if self._view_model is not None
            else "Application foundation is ready"
        )
        self._empty_title.setObjectName("emptyTitle")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_detail = QLabel(
            "Enter a product name to search the local database."
            if self._view_model is not None
            else (
                "Search becomes available when the application\n"
                "is composed with its local database."
            )
        )
        self._empty_detail.setObjectName("muted")
        self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._empty_title)
        layout.addWidget(self._empty_detail)
        return frame

    def _connect_view_model(self) -> None:
        if self._view_model is None:
            return
        self._search_button.clicked.connect(self._start_search)
        self._search_input.returnPressed.connect(self._start_search)
        self._load_more_button.clicked.connect(self._view_model.load_more)
        self._recent_list.itemActivated.connect(self._activate_recent)
        self._view_model.loading_changed.connect(self._on_loading_changed)
        self._view_model.status_changed.connect(self._on_status_changed)
        self._view_model.has_more_changed.connect(self._load_more_button.setVisible)
        self._view_model.recent_changed.connect(self._on_recent_changed)

    @Slot()
    def _start_search(self) -> None:
        if self._view_model is not None:
            self._view_model.search(self._search_input.text())

    @Slot(bool)
    def _on_loading_changed(self, loading: bool) -> None:
        self._search_button.setDisabled(loading)
        self._search_input.setDisabled(loading)
        self._load_more_button.setDisabled(loading)

    @Slot(str)
    def _on_status_changed(self, message: str) -> None:
        self.statusBar().showMessage(message)
        has_rows = (
            self._view_model is not None and self._view_model.table_model.rowCount() > 0
        )
        self._result_table.setVisible(has_rows)
        self._empty_state.setVisible(not has_rows)
        if not has_rows and not message.startswith("Searching"):
            self._empty_title.setText("No local sales found")
            self._empty_detail.setText(
                "Import sales data or adjust the search phrase and filters."
            )

    @Slot(object)
    def _on_recent_changed(self, raw_recent: object) -> None:
        if not isinstance(raw_recent, tuple):
            return
        self._recent_list.clear()
        for recent in raw_recent:
            if isinstance(recent, RecentSearch):
                item = QListWidgetItem(f"{recent.query}  ·  {recent.use_count}")
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    recent.query,
                )
                self._recent_list.addItem(item)
        self._recent_list.setVisible(self._recent_list.count() > 0)

    @Slot(QListWidgetItem)
    def _activate_recent(self, item: QListWidgetItem) -> None:
        query = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(query, str):
            self._search_input.setText(query)
            self._start_search()

    @staticmethod
    def _navigation_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("eyebrow")
        return label

    @staticmethod
    def _muted_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        label.setContentsMargins(0, 6, 0, 6)
        return label
