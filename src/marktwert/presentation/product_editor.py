"""Tracked-product criteria editor dialog."""

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from marktwert.domain.money import Money
from marktwert.domain.sales import (
    CompletedSalesCriteria,
    ItemCondition,
    ListingFormat,
    PriceBasis,
    TrackedProduct,
)

MAXIMUM_UI_PRICE = 1_000_000


@dataclass(frozen=True, slots=True)
class ProductFormData:
    """Validated values returned by the product editor."""

    name: str
    criteria: CompletedSalesCriteria
    enabled: bool


class TrackedProductEditor(QDialog):
    """Edit all pre-collection criteria for one tracked product."""

    def __init__(
        self,
        product: TrackedProduct | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build and optionally populate the modal editor."""
        super().__init__(parent)
        self._product = product
        self.setWindowTitle("Edit tracked product" if product else "Add tracked product")
        self.setMinimumWidth(560)
        self._build_ui()
        if product is not None:
            self._populate(product)

    def form_data(self) -> ProductFormData:
        """Return validated form values."""
        conditions = frozenset(
            condition
            for condition, checkbox in (
                (ItemCondition.NEW, self._new_condition),
                (ItemCondition.USED, self._used_condition),
            )
            if checkbox.isChecked()
        )
        listing_formats = frozenset(
            listing_format
            for listing_format, checkbox in (
                (ListingFormat.AUCTION, self._auction_format),
                (ListingFormat.BUY_IT_NOW, self._buy_it_now_format),
            )
            if checkbox.isChecked()
        )
        currency = "EUR"
        minimum_price = (
            Money.from_major_units(
                Decimal(str(self._minimum_price.value())),
                currency,
            )
            if self._minimum_price_enabled.isChecked()
            else None
        )
        maximum_price = (
            Money.from_major_units(
                Decimal(str(self._maximum_price.value())),
                currency,
            )
            if self._maximum_price_enabled.isChecked()
            else None
        )
        return ProductFormData(
            name=self._name.text(),
            enabled=self._enabled.isChecked(),
            criteria=CompletedSalesCriteria(
                query=self._query.text(),
                category_id=self._category_id.text() or None,
                brand=self._brand.text() or None,
                minimum_price=minimum_price,
                maximum_price=maximum_price,
                price_basis=PriceBasis(cast(str, self._price_basis.currentData())),
                conditions=conditions,
                listing_formats=listing_formats,
                lookback_days=self._lookback_days.value(),
                standalone_working_only=self._standalone_working.isChecked(),
                required_title_terms=_split_terms(self._required_terms.text()),
                additional_exclusion_terms=_split_terms(
                    self._exclusion_terms.text()
                ),
            ),
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        introduction = QLabel(
            "These criteria are saved before collection and applied again "
            "during local classification."
        )
        introduction.setWordWrap(True)
        introduction.setObjectName("muted")
        root.addWidget(introduction)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._name = QLineEdit()
        self._name.setObjectName("productName")
        self._query = QLineEdit()
        self._query.setObjectName("productQuery")
        self._brand = QLineEdit()
        self._category_id = QLineEdit()
        self._enabled = QCheckBox("Automatic collection enabled")
        self._enabled.setChecked(True)
        form.addRow("Display name", self._name)
        form.addRow("eBay search phrase", self._query)
        form.addRow("Brand (optional)", self._brand)
        form.addRow("eBay category ID", self._category_id)
        form.addRow("", self._enabled)

        self._lookback_days = QSpinBox()
        self._lookback_days.setRange(1, 90)
        self._lookback_days.setValue(30)
        self._lookback_days.setSuffix(" days")
        form.addRow("Sold-data window", self._lookback_days)

        self._price_basis = QComboBox()
        self._price_basis.addItem(
            "Item plus shipping",
            PriceBasis.ITEM_AND_SHIPPING.value,
        )
        self._price_basis.addItem("Item price only", PriceBasis.ITEM_PRICE.value)
        form.addRow("Price criteria use", self._price_basis)
        form.addRow("Minimum price", self._build_price_control(minimum=True))
        form.addRow("Maximum price", self._build_price_control(minimum=False))
        root.addLayout(form)

        root.addWidget(self._build_condition_group())
        root.addWidget(self._build_listing_format_group())

        filter_form = QFormLayout()
        self._standalone_working = QCheckBox(
            "Exclude faulty, empty-box, accessory-only, and parts listings"
        )
        self._standalone_working.setChecked(True)
        self._required_terms = QLineEdit()
        self._required_terms.setPlaceholderText("For example: 8 GB, Gaming OC")
        self._exclusion_terms = QLineEdit()
        self._exclusion_terms.setPlaceholderText("For example: water block")
        filter_form.addRow("", self._standalone_working)
        filter_form.addRow("Required title terms", self._required_terms)
        filter_form.addRow("Additional exclusions", self._exclusion_terms)
        root.addLayout(filter_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_price_control(self, *, minimum: bool) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        checkbox = QCheckBox("Use limit")
        spinbox = QDoubleSpinBox()
        prefix = "minimum" if minimum else "maximum"
        checkbox.setObjectName(f"{prefix}PriceEnabled")
        spinbox.setObjectName(f"{prefix}Price")
        spinbox.setDecimals(2)
        spinbox.setRange(0, MAXIMUM_UI_PRICE)
        spinbox.setSuffix(" EUR")
        spinbox.setEnabled(False)
        checkbox.toggled.connect(spinbox.setEnabled)
        layout.addWidget(checkbox)
        layout.addWidget(spinbox, stretch=1)
        if minimum:
            self._minimum_price_enabled = checkbox
            self._minimum_price = spinbox
        else:
            self._maximum_price_enabled = checkbox
            self._maximum_price = spinbox
        return container

    def _build_condition_group(self) -> QGroupBox:
        group = QGroupBox("Conditions")
        layout = QHBoxLayout(group)
        self._new_condition = QCheckBox("New")
        self._used_condition = QCheckBox("Used")
        self._new_condition.setChecked(True)
        self._used_condition.setChecked(True)
        layout.addWidget(self._new_condition)
        layout.addWidget(self._used_condition)
        layout.addStretch()
        return group

    def _build_listing_format_group(self) -> QGroupBox:
        group = QGroupBox("Listing formats")
        layout = QHBoxLayout(group)
        self._auction_format = QCheckBox("Auction")
        self._buy_it_now_format = QCheckBox("Buy It Now")
        self._auction_format.setChecked(True)
        self._buy_it_now_format.setChecked(True)
        layout.addWidget(self._auction_format)
        layout.addWidget(self._buy_it_now_format)
        layout.addStretch()
        return group

    def _populate(self, product: TrackedProduct) -> None:
        criteria = product.criteria
        self._name.setText(product.name)
        self._query.setText(criteria.query)
        self._brand.setText(criteria.brand or "")
        self._category_id.setText(criteria.category_id or "")
        self._enabled.setChecked(product.enabled)
        self._lookback_days.setValue(criteria.lookback_days)
        index = self._price_basis.findData(criteria.price_basis.value)
        self._price_basis.setCurrentIndex(index)
        self._set_price(
            criteria.minimum_price,
            self._minimum_price_enabled,
            self._minimum_price,
        )
        self._set_price(
            criteria.maximum_price,
            self._maximum_price_enabled,
            self._maximum_price,
        )
        self._new_condition.setChecked(ItemCondition.NEW in criteria.conditions)
        self._used_condition.setChecked(ItemCondition.USED in criteria.conditions)
        self._auction_format.setChecked(
            ListingFormat.AUCTION in criteria.listing_formats
        )
        self._buy_it_now_format.setChecked(
            ListingFormat.BUY_IT_NOW in criteria.listing_formats
        )
        self._standalone_working.setChecked(criteria.standalone_working_only)
        self._required_terms.setText(", ".join(criteria.required_title_terms))
        self._exclusion_terms.setText(
            ", ".join(criteria.additional_exclusion_terms)
        )

    @staticmethod
    def _set_price(
        price: Money | None,
        checkbox: QCheckBox,
        spinbox: QDoubleSpinBox,
    ) -> None:
        checkbox.setChecked(price is not None)
        if price is not None:
            spinbox.setValue(float(price.major_units))

    @Slot()
    def _validate_and_accept(self) -> None:
        try:
            self.form_data()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid product criteria", str(error))
            return
        self.accept()


def _split_terms(value: str) -> tuple[str, ...]:
    return tuple(term.strip() for term in value.split(",") if term.strip())
