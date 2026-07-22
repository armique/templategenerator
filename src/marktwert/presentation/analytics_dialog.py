"""Market statistics and price-history dialog."""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.dates import date2num
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from marktwert.application.analytics import AnalysisWindow, MarketAnalysis
from marktwert.domain.money import Money
from marktwert.domain.sales import TrackedProduct
from marktwert.presentation.analytics_view_model import AnalyticsViewModel


class MarketAnalysisDialog(QDialog):
    """Display reproducible statistics and chart-ready local history."""

    def __init__(
        self,
        view_model: AnalyticsViewModel,
        parent: QWidget | None = None,
    ) -> None:
        """Build the analysis workspace and load products."""
        super().__init__(parent)
        self._view_model = view_model
        self.setWindowTitle("Market analysis")
        self.resize(1050, 720)
        self._build_ui()
        self._connect()
        self._view_model.load_products()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Market statistics and price history")
        title.setObjectName("pageTitle")
        controls = QHBoxLayout()
        self._products = QComboBox()
        self._products.setObjectName("analysisProduct")
        self._window = QComboBox()
        for window, label in (
            (AnalysisWindow.DAYS_7, "7 days"),
            (AnalysisWindow.DAYS_30, "30 days"),
            (AnalysisWindow.DAYS_90, "90 days"),
            (AnalysisWindow.DAYS_180, "180 days"),
            (AnalysisWindow.DAYS_365, "365 days"),
            (AnalysisWindow.ALL_TIME, "All time"),
        ):
            self._window.addItem(label, window)
        self._window.setCurrentIndex(1)
        self._shipping = QCheckBox("Include shipping")
        self._shipping.setChecked(True)
        self._analyze = QPushButton("Analyze")
        self._analyze.setObjectName("analyzeButton")
        self._analyze.setEnabled(False)
        controls.addWidget(self._products, stretch=1)
        controls.addWidget(self._window)
        controls.addWidget(self._shipping)
        controls.addWidget(self._analyze)

        metrics = QFormLayout()
        self._metric_labels: dict[str, QLabel] = {}
        for key, label in (
            ("sample", "Total sold"),
            ("average", "Average price"),
            ("median", "Median price"),
            ("range", "Price range"),
            ("stddev", "Standard deviation"),
            ("shipping", "Average shipping"),
            ("frequency", "Daily / weekly / monthly"),
            ("trend", "Trend"),
            ("volatility", "Volatility"),
        ):
            value = QLabel("—")
            value.setObjectName(f"metric{key.title()}")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._metric_labels[key] = value
            metrics.addRow(label, value)

        self._figure = Figure(facecolor="#151a21")
        self._canvas = FigureCanvasQTAgg(self._figure)  # type: ignore[no-untyped-call]
        self._status = QLabel("Select a tracked product.")
        self._status.setObjectName("muted")

        root.addWidget(title)
        root.addLayout(controls)
        root.addLayout(metrics)
        root.addWidget(self._canvas, stretch=1)
        root.addWidget(self._status)

    def _connect(self) -> None:
        self._analyze.clicked.connect(self._request_analysis)
        self._view_model.busy_changed.connect(self._on_busy)
        self._view_model.products_changed.connect(self._on_products)
        self._view_model.analysis_ready.connect(self._on_analysis)
        self._view_model.error_raised.connect(self._on_error)

    @Slot()
    def _request_analysis(self) -> None:
        product = self._products.currentData()
        window = self._window.currentData()
        if isinstance(product, TrackedProduct) and isinstance(window, AnalysisWindow):
            self._view_model.analyze(
                product.id,
                window,
                include_shipping=self._shipping.isChecked(),
            )

    @Slot(bool)
    def _on_busy(self, busy: bool) -> None:
        self._analyze.setDisabled(busy or self._products.count() == 0)
        self._status.setText("Calculating…" if busy else self._status.text())

    @Slot(object)
    def _on_products(self, raw_products: object) -> None:
        self._products.clear()
        if isinstance(raw_products, tuple):
            for product in raw_products:
                if isinstance(product, TrackedProduct):
                    self._products.addItem(product.name, product)
        self._analyze.setEnabled(self._products.count() > 0)

    @Slot(object)
    def _on_analysis(self, raw_analysis: object) -> None:
        if not isinstance(raw_analysis, MarketAnalysis):
            return
        statistics = raw_analysis.statistics
        if statistics is None:
            self._status.setText("No accepted sales in this time window.")
            self._clear_chart()
            return
        self._metric_labels["sample"].setText(str(statistics.sample_size))
        self._metric_labels["average"].setText(_money(statistics.average))
        self._metric_labels["median"].setText(_money(statistics.median))
        self._metric_labels["range"].setText(
            f"{_money(statistics.minimum)} - {_money(statistics.maximum)}"
        )
        self._metric_labels["stddev"].setText(_money(statistics.standard_deviation))
        self._metric_labels["shipping"].setText(_money(statistics.average_shipping))
        self._metric_labels["frequency"].setText(
            f"{statistics.average_daily_sales} / "
            f"{statistics.average_weekly_sales} / "
            f"{statistics.average_monthly_sales}"
        )
        self._metric_labels["trend"].setText(
            f"{statistics.trend_percent:+} %"
            if statistics.trend_percent is not None
            else "Insufficient sample"
        )
        self._metric_labels["volatility"].setText(f"{statistics.volatility_percent} %")
        self._draw_history(raw_analysis)
        self._status.setText(
            f"{statistics.first_sale_date:%d.%m.%Y} - "
            f"{statistics.last_sale_date:%d.%m.%Y}"
        )

    def _draw_history(self, analysis: MarketAnalysis) -> None:
        self._figure.clear()
        axis = self._figure.add_subplot(111)
        axis.set_facecolor("#151a21")
        dates = date2num([point.sold_at for point in analysis.history])
        prices = [float(point.price.major_units) for point in analysis.history]
        moving = [float(point.moving_average.major_units) for point in analysis.history]
        axis.scatter(dates, prices, color="#7fa2ff", s=24, label="Sold price")
        axis.plot(dates, moving, color="#49c6a2", linewidth=2, label="7-day average")
        axis.tick_params(colors="#9ba6b5")
        axis.grid(color="#252c36", alpha=0.7)
        axis.legend(facecolor="#191f27", labelcolor="#e6eaf0")
        self._figure.tight_layout()
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    def _clear_chart(self) -> None:
        self._figure.clear()
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    @Slot(str)
    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Market analysis", message)


def _money(value: Money) -> str:
    major = value.major_units
    return f"{major:.2f} {value.currency}"
