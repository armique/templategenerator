"""Main application window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from marktwert import APPLICATION


class MainWindow(QMainWindow):
    """Display the responsive application shell."""

    def __init__(self) -> None:
        """Initialize the main window and its foundation state."""
        super().__init__()
        self.setWindowTitle(APPLICATION.name)
        self.setMinimumSize(960, 640)
        self.resize(1280, 800)
        self.setCentralWidget(self._build_content())
        self.statusBar().showMessage("Foundation ready · No data source configured")

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

        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(32)
        layout.addWidget(self._navigation_label("OVERVIEW"))
        layout.addWidget(self._muted_label("Search"))
        layout.addWidget(self._muted_label("Favorites"))
        layout.addWidget(self._muted_label("Watchlists"))
        layout.addSpacing(24)
        layout.addWidget(self._navigation_label("ANALYSIS"))
        layout.addWidget(self._muted_label("Market"))
        layout.addWidget(self._muted_label("Deal finder"))
        layout.addStretch()
        layout.addWidget(self._muted_label(f"Version {APPLICATION.version}"))
        return sidebar

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(48, 38, 48, 32)
        layout.setSpacing(22)

        eyebrow = QLabel("EBAY GERMANY · COMPUTER HARDWARE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Market overview")
        title.setObjectName("pageTitle")

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addLayout(self._build_search())
        layout.addWidget(self._build_empty_state(), stretch=1)
        return workspace

    def _build_search(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        search = QLineEdit()
        search.setPlaceholderText("Search, for example RTX 3070")
        search.setAccessibleName("Product search")
        search.setDisabled(True)
        search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        button = QPushButton("Search")
        button.setAccessibleName("Search completed sales")
        button.setDisabled(True)

        layout.addWidget(search, stretch=1)
        layout.addWidget(button)
        return layout

    def _build_empty_state(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("emptyState")

        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(10)

        title = QLabel("Application foundation is ready")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detail = QLabel(
            "Search will become available after the sales domain,\n"
            "persistence, and an authorized data source are configured."
        )
        detail.setObjectName("muted")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(detail)
        return frame

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
