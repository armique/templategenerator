"""Exact monetary value objects."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

MINOR_UNITS_PER_MAJOR_UNIT = 100


@dataclass(frozen=True, slots=True)
class Money:
    """Represent money as integer minor units in one ISO-4217 currency."""

    minor_units: int
    currency: str = "EUR"

    def __post_init__(self) -> None:
        """Validate and normalize the monetary value."""
        normalized_currency = self.currency.strip().upper()
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            message = "currency must be a three-letter ISO-4217 code"
            raise ValueError(message)
        object.__setattr__(self, "currency", normalized_currency)

    @classmethod
    def from_major_units(
        cls,
        amount: Decimal | str,
        currency: str = "EUR",
    ) -> "Money":
        """Create money from a decimal major-unit amount."""
        decimal_amount = Decimal(amount)
        minor_units = int(
            (decimal_amount * MINOR_UNITS_PER_MAJOR_UNIT).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        return cls(minor_units=minor_units, currency=currency)

    @property
    def major_units(self) -> Decimal:
        """Return the exact decimal major-unit amount."""
        return Decimal(self.minor_units) / MINOR_UNITS_PER_MAJOR_UNIT
