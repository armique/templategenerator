"""Tracked-product management and completed-sales import workspace."""

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from marktwert.application.imports import ImportPreview, ImportReport
from marktwert.domain.sales import TrackedProduct
from marktwert.presentation.product_editor import TrackedProductEditor
from marktwert.presentation.product_view_model import ProductWorkspaceViewModel


class ProductWorkspaceDialog(QDialog):
    """Manage collection profiles and import historical sales."""

    def __init__(
        self,
        view_model: ProductWorkspaceViewModel,
        parent: QWidget | None = None,
    ) -> None:
        """Build the model-driven product and import workspace."""
        super().__init__(parent)
        self._view_model = view_model
        self._preview_ready = False
        self.setWindowTitle("Tracked products and imports")
        self.resize(1050, 700)
        self.setMinimumSize(850, 560)
        self._build_ui()
        self._connect_view_model()
        self._view_model.refresh_products()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        heading = QLabel("Tracked products")
        heading.setObjectName("pageTitle")
        root.addWidget(heading)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_product_panel())
        splitter.addWidget(self._build_import_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        self._status = QLabel("Loading tracked products…")
        self._status.setObjectName("muted")
        root.addWidget(self._status)

    def _build_product_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 12, 0)
        self._product_list = QListWidget()
        self._product_list.setObjectName("trackedProductList")
        self._product_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._product_details = QLabel("Select or add a tracked product.")
        self._product_details.setWordWrap(True)
        self._product_details.setObjectName("muted")

        button_row = QHBoxLayout()
        self._add_button = QPushButton("Add")
        self._add_button.setObjectName("addProductButton")
        self._edit_button = QPushButton("Edit")
        self._remove_button = QPushButton("Remove")
        self._edit_button.setEnabled(False)
        self._remove_button.setEnabled(False)
        button_row.addWidget(self._add_button)
        button_row.addWidget(self._edit_button)
        button_row.addWidget(self._remove_button)

        layout.addWidget(self._product_list, stretch=1)
        layout.addWidget(self._product_details)
        layout.addLayout(button_row)
        return panel

    def _build_import_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 0, 0, 0)
        title = QLabel("Import completed sales")
        title.setObjectName("emptyTitle")
        explanation = QLabel(
            "Preview a UTF-8 CSV or XLSX file before committing valid rows. "
            "Excluded and review rows remain auditable."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("muted")

        file_row = QHBoxLayout()
        self._file_path = QLineEdit()
        self._file_path.setObjectName("importFilePath")
        self._file_path.setReadOnly(True)
        self._file_path.setPlaceholderText("Choose a CSV or XLSX file")
        self._browse_button = QPushButton("Browse…")
        file_row.addWidget(self._file_path, stretch=1)
        file_row.addWidget(self._browse_button)

        action_row = QHBoxLayout()
        self._preview_button = QPushButton("Preview")
        self._preview_button.setObjectName("previewImportButton")
        self._import_button = QPushButton("Import valid rows")
        self._import_button.setObjectName("executeImportButton")
        self._preview_button.setEnabled(False)
        self._import_button.setEnabled(False)
        action_row.addWidget(self._preview_button)
        action_row.addWidget(self._import_button)
        action_row.addStretch()

        self._preview_table = QTableWidget(0, 5)
        self._preview_table.setObjectName("importPreviewTable")
        self._preview_table.setHorizontalHeaderLabels(
            ("Row", "Title", "Total", "Sold", "Decision")
        )
        self._preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._preview_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addLayout(file_row)
        layout.addLayout(action_row)
        layout.addWidget(self._preview_table, stretch=1)
        return panel

    def _connect_view_model(self) -> None:
        self._add_button.clicked.connect(self._add_product)
        self._edit_button.clicked.connect(self._edit_product)
        self._remove_button.clicked.connect(self._remove_product)
        self._product_list.currentItemChanged.connect(self._selection_changed)
        self._browse_button.clicked.connect(self._browse_file)
        self._preview_button.clicked.connect(self._preview_import)
        self._import_button.clicked.connect(self._execute_import)
        self._view_model.busy_changed.connect(self._on_busy_changed)
        self._view_model.status_changed.connect(self._status.setText)
        self._view_model.products_changed.connect(self._on_products_changed)
        self._view_model.preview_ready.connect(self._on_preview_ready)
        self._view_model.import_finished.connect(self._on_import_finished)
        self._view_model.error_raised.connect(self._on_error)

    def _selected_product(self) -> TrackedProduct | None:
        item = self._product_list.currentItem()
        if item is None:
            return None
        product = item.data(Qt.ItemDataRole.UserRole)
        return product if isinstance(product, TrackedProduct) else None

    @Slot()
    def _add_product(self) -> None:
        editor = TrackedProductEditor(parent=self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        data = editor.form_data()
        self._view_model.create_product(name=data.name, criteria=data.criteria)

    @Slot()
    def _edit_product(self) -> None:
        product = self._selected_product()
        if product is None:
            return
        editor = TrackedProductEditor(product, self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        data = editor.form_data()
        self._view_model.update_product(
            product,
            name=data.name,
            criteria=data.criteria,
            enabled=data.enabled,
        )

    @Slot()
    def _remove_product(self) -> None:
        product = self._selected_product()
        if product is None:
            return
        answer = QMessageBox.question(
            self,
            "Remove tracked product",
            (
                f"Remove “{product.name}”? Imported observations remain in "
                "the local database."
            ),
        )
        if answer is QMessageBox.StandardButton.Yes:
            self._view_model.remove_product(product.id)

    @Slot()
    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose completed-sales file",
            "",
            "Sales files (*.csv *.xlsx)",
        )
        if path:
            self._file_path.setText(path)
            self._preview_ready = False
            self._preview_table.setRowCount(0)
            self._update_import_actions()

    @Slot()
    def _preview_import(self) -> None:
        product = self._selected_product()
        if product is None or not self._file_path.text():
            return
        self._preview_ready = False
        self._update_import_actions()
        self._view_model.preview_import(product.id, Path(self._file_path.text()))

    @Slot()
    def _execute_import(self) -> None:
        product = self._selected_product()
        if (
            product is None
            or not self._file_path.text()
            or not self._preview_ready
        ):
            return
        self._view_model.import_file(product.id, Path(self._file_path.text()))

    @Slot(object)
    def _on_products_changed(self, raw_products: object) -> None:
        if not isinstance(raw_products, tuple):
            return
        selected_id = (
            self._selected_product().id if self._selected_product() else None
        )
        self._product_list.clear()
        selected_row = 0
        for index, product in enumerate(raw_products):
            if not isinstance(product, TrackedProduct):
                continue
            state = "enabled" if product.enabled else "disabled"
            item = QListWidgetItem(f"{product.name}  ·  {state}")
            item.setData(Qt.ItemDataRole.UserRole, product)
            self._product_list.addItem(item)
            if selected_id == product.id:
                selected_row = index
        if self._product_list.count():
            self._product_list.setCurrentRow(selected_row)
        self._update_import_actions()

    @Slot(QListWidgetItem, QListWidgetItem)
    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        product = (
            current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        )
        has_product = isinstance(product, TrackedProduct)
        self._edit_button.setEnabled(has_product and not self._view_model.is_busy)
        self._remove_button.setEnabled(has_product and not self._view_model.is_busy)
        if isinstance(product, TrackedProduct):
            criteria = product.criteria
            maximum = (
                f"{criteria.maximum_price.major_units:.2f} EUR"
                if criteria.maximum_price
                else "No maximum"
            )
            self._product_details.setText(
                f"Query: {criteria.query}\n"
                f"Window: {criteria.lookback_days} days\n"
                f"Maximum: {maximum}"
            )
        else:
            self._product_details.setText("Select or add a tracked product.")
        self._preview_ready = False
        self._preview_table.setRowCount(0)
        self._update_import_actions()

    @Slot(object)
    def _on_preview_ready(self, raw_preview: object) -> None:
        if not isinstance(raw_preview, ImportPreview):
            return
        self._preview_table.setRowCount(len(raw_preview.rows))
        for row_index, preview_row in enumerate(raw_preview.rows):
            values = (
                str(preview_row.row_number),
                preview_row.title,
                f"{preview_row.total_price.major_units:.2f} EUR",
                preview_row.sold_at.astimezone().strftime("%d.%m.%Y"),
                preview_row.classification.decision.value.title(),
            )
            for column, value in enumerate(values):
                self._preview_table.setItem(
                    row_index,
                    column,
                    QTableWidgetItem(value),
                )
        self._preview_ready = bool(raw_preview.rows)
        self._update_import_actions()
        if raw_preview.issues:
            self._status.setText(
                f"{len(raw_preview.rows)} preview rows; "
                f"{len(raw_preview.issues)} issues"
            )

    @Slot(object)
    def _on_import_finished(self, raw_report: object) -> None:
        if not isinstance(raw_report, ImportReport):
            return
        self._preview_ready = False
        self._import_button.setEnabled(False)
        QMessageBox.information(
            self,
            "Import complete",
            (
                f"Created: {raw_report.created_observations}\n"
                f"Enriched: {raw_report.enriched_observations}\n"
                f"Duplicates: {raw_report.duplicate_observations}\n"
                f"Invalid: {raw_report.invalid_rows}"
            ),
        )

    @Slot(str)
    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Product workspace", message)

    @Slot(bool)
    def _on_busy_changed(self, busy: bool) -> None:
        self._add_button.setDisabled(busy)
        self._browse_button.setDisabled(busy)
        has_product = self._selected_product() is not None
        self._edit_button.setEnabled(has_product and not busy)
        self._remove_button.setEnabled(has_product and not busy)
        self._update_import_actions()

    def _update_import_actions(self) -> None:
        ready = (
            self._selected_product() is not None
            and bool(self._file_path.text())
            and not self._view_model.is_busy
        )
        self._preview_button.setEnabled(ready)
        self._import_button.setEnabled(ready and self._preview_ready)
