"""Tracked-product configuration for completed-sale collection."""

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from marktwert.domain.money import ISO_4217_CODE_LENGTH, Money

ISO_3166_ALPHA_2_CODE_LENGTH = 2
DEFAULT_LOOKBACK_DAYS = 30
MAXIMUM_LOOKBACK_DAYS = 90
MINIMUM_QUERY_LENGTH = 2
MAXIMUM_QUERY_LENGTH = 200
MAXIMUM_FILTER_TERM_LENGTH = 100


class ItemCondition(StrEnum):
    """Marketplace condition groups supported by collection profiles."""

    NEW = "new"
    USED = "used"


class ListingFormat(StrEnum):
    """Sale formats supported by completed-sale searches."""

    AUCTION = "auction"
    BUY_IT_NOW = "buy_it_now"


class PriceBasis(StrEnum):
    """Select whether shipping contributes to configured price limits."""

    ITEM_PRICE = "item_price"
    ITEM_AND_SHIPPING = "item_and_shipping"


@dataclass(frozen=True, slots=True)
class TrackedProductId:
    """Strongly typed identity for a tracked product."""

    value: UUID

    @classmethod
    def new(cls) -> "TrackedProductId":
        """Create a unique tracked-product identity."""
        return cls(uuid4())


@dataclass(frozen=True, slots=True)
class CompletedSalesCriteria:
    """Validated criteria for one targeted completed-sales search."""

    query: str
    category_id: str | None = None
    brand: str | None = None
    minimum_price: Money | None = None
    maximum_price: Money | None = None
    price_basis: PriceBasis = PriceBasis.ITEM_AND_SHIPPING
    conditions: frozenset[ItemCondition] = field(
        default_factory=lambda: frozenset(ItemCondition)
    )
    listing_formats: frozenset[ListingFormat] = field(
        default_factory=lambda: frozenset(ListingFormat)
    )
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    marketplace_country: str = "DE"
    currency: str = "EUR"
    standalone_working_only: bool = True
    required_title_terms: tuple[str, ...] = ()
    additional_exclusion_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize text and enforce collection invariants."""
        normalized_query = " ".join(self.query.split())
        if not MINIMUM_QUERY_LENGTH <= len(normalized_query) <= MAXIMUM_QUERY_LENGTH:
            message = (
                f"query length must be between {MINIMUM_QUERY_LENGTH} "
                f"and {MAXIMUM_QUERY_LENGTH} characters"
            )
            raise ValueError(message)

        normalized_country = self.marketplace_country.strip().upper()
        if (
            len(normalized_country) != ISO_3166_ALPHA_2_CODE_LENGTH
            or not normalized_country.isalpha()
        ):
            message = "marketplace_country must be a two-letter country code"
            raise ValueError(message)

        normalized_currency = self.currency.strip().upper()
        if (
            len(normalized_currency) != ISO_4217_CODE_LENGTH
            or not normalized_currency.isalpha()
        ):
            message = "currency must be a three-letter ISO-4217 code"
            raise ValueError(message)

        if not 1 <= self.lookback_days <= MAXIMUM_LOOKBACK_DAYS:
            message = f"lookback_days must be between 1 and {MAXIMUM_LOOKBACK_DAYS}"
            raise ValueError(message)
        if not self.conditions:
            message = "at least one item condition must be selected"
            raise ValueError(message)
        if not self.listing_formats:
            message = "at least one listing format must be selected"
            raise ValueError(message)

        for price in (self.minimum_price, self.maximum_price):
            if price is not None and price.currency != normalized_currency:
                message = "price currency must match criteria currency"
                raise ValueError(message)
            if price is not None and price.minor_units < 0:
                message = "price limits cannot be negative"
                raise ValueError(message)
        if (
            self.minimum_price is not None
            and self.maximum_price is not None
            and self.minimum_price.minor_units > self.maximum_price.minor_units
        ):
            message = "minimum_price cannot exceed maximum_price"
            raise ValueError(message)

        category_id = self.category_id.strip() if self.category_id else None
        if category_id is not None and not category_id.isdecimal():
            message = "category_id must contain digits only"
            raise ValueError(message)

        brand = " ".join(self.brand.split()) if self.brand else None
        required_title_terms = _normalize_terms(self.required_title_terms)
        additional_exclusion_terms = _normalize_terms(
            self.additional_exclusion_terms
        )
        object.__setattr__(self, "query", normalized_query)
        object.__setattr__(self, "category_id", category_id)
        object.__setattr__(self, "brand", brand)
        object.__setattr__(self, "marketplace_country", normalized_country)
        object.__setattr__(self, "currency", normalized_currency)
        object.__setattr__(self, "required_title_terms", required_title_terms)
        object.__setattr__(
            self,
            "additional_exclusion_terms",
            additional_exclusion_terms,
        )

    @property
    def sold_only(self) -> bool:
        """Confirm that this criteria type represents completed sales only."""
        return True


@dataclass(frozen=True, slots=True)
class TrackedProduct:
    """A user-managed product and its completed-sale criteria."""

    id: TrackedProductId
    name: str
    criteria: CompletedSalesCriteria
    enabled: bool = True

    def __post_init__(self) -> None:
        """Normalize and validate the display name."""
        normalized_name = " ".join(self.name.split())
        if not normalized_name:
            message = "tracked product name cannot be empty"
            raise ValueError(message)
        object.__setattr__(self, "name", normalized_name)

    @classmethod
    def create(
        cls,
        name: str,
        criteria: CompletedSalesCriteria,
    ) -> "TrackedProduct":
        """Create a new enabled tracked product."""
        return cls(id=TrackedProductId.new(), name=name, criteria=criteria)

    def edit(
        self,
        *,
        name: str | None = None,
        criteria: CompletedSalesCriteria | None = None,
    ) -> Self:
        """Return an edited copy while preserving identity."""
        return replace(
            self,
            name=self.name if name is None else name,
            criteria=self.criteria if criteria is None else criteria,
        )

    def set_enabled(self, *, enabled: bool) -> Self:
        """Return a copy with collection enabled or disabled."""
        return replace(self, enabled=enabled)


def _normalize_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    normalized_terms = tuple(dict.fromkeys(" ".join(term.split()) for term in terms))
    if any(not term for term in normalized_terms):
        message = "title filter terms cannot be empty"
        raise ValueError(message)
    if any(len(term) > MAXIMUM_FILTER_TERM_LENGTH for term in normalized_terms):
        message = (
            f"title filter terms cannot exceed {MAXIMUM_FILTER_TERM_LENGTH} characters"
        )
        raise ValueError(message)
    return normalized_terms
