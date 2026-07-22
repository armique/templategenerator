"""Typed local completed-sales search models."""

from dataclasses import dataclass, field
from datetime import datetime

from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ClassificationDecision,
    ItemCondition,
    ListingFormat,
    TrackedProductId,
)

DEFAULT_SEARCH_PAGE_SIZE = 50
MAXIMUM_SEARCH_PAGE_SIZE = 200
MAXIMUM_SEARCH_QUERY_LENGTH = 200


@dataclass(frozen=True, slots=True)
class SearchCursor:
    """Stable keyset cursor for descending sale-date pagination."""

    sold_at: datetime
    observation_id: int

    def __post_init__(self) -> None:
        """Require an aware timestamp and durable positive identity."""
        if self.sold_at.tzinfo is None:
            message = "search cursor timestamp must be timezone-aware"
            raise ValueError(message)
        if self.observation_id <= 0:
            message = "search cursor observation_id must be positive"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class SaleSearchFilters:
    """Optional local-database filters applied before pagination."""

    tracked_product_id: TrackedProductId | None = None
    minimum_price: Money | None = None
    maximum_price: Money | None = None
    sold_from: datetime | None = None
    sold_to: datetime | None = None
    conditions: frozenset[ItemCondition] = field(default_factory=frozenset)
    listing_formats: frozenset[ListingFormat] = field(default_factory=frozenset)
    classifications: frozenset[ClassificationDecision] = field(
        default_factory=lambda: frozenset({ClassificationDecision.ACCEPT})
    )

    def __post_init__(self) -> None:
        """Validate money, date, and classification boundaries."""
        if not self.classifications:
            message = "at least one classification must be selected"
            raise ValueError(message)
        for timestamp in (self.sold_from, self.sold_to):
            if timestamp is not None and timestamp.tzinfo is None:
                message = "search date filters must be timezone-aware"
                raise ValueError(message)
        if (
            self.sold_from is not None
            and self.sold_to is not None
            and self.sold_from > self.sold_to
        ):
            message = "sold_from cannot be later than sold_to"
            raise ValueError(message)
        if self.minimum_price is not None and self.minimum_price.minor_units < 0:
            message = "minimum search price cannot be negative"
            raise ValueError(message)
        if self.maximum_price is not None and self.maximum_price.minor_units < 0:
            message = "maximum search price cannot be negative"
            raise ValueError(message)
        if self.minimum_price is not None and self.maximum_price is not None:
            if self.minimum_price.currency != self.maximum_price.currency:
                message = "search price currencies must match"
                raise ValueError(message)
            if self.minimum_price.minor_units > self.maximum_price.minor_units:
                message = "minimum search price cannot exceed maximum"
                raise ValueError(message)


@dataclass(frozen=True, slots=True)
class SearchSales:
    """Request one local completed-sales result page."""

    query: str = ""
    filters: SaleSearchFilters = field(default_factory=SaleSearchFilters)
    page_size: int = DEFAULT_SEARCH_PAGE_SIZE
    cursor: SearchCursor | None = None

    def __post_init__(self) -> None:
        """Normalize the query and enforce bounded result pages."""
        normalized_query = " ".join(self.query.split())
        if len(normalized_query) > MAXIMUM_SEARCH_QUERY_LENGTH:
            message = (
                f"search query cannot exceed {MAXIMUM_SEARCH_QUERY_LENGTH} characters"
            )
            raise ValueError(message)
        if not 1 <= self.page_size <= MAXIMUM_SEARCH_PAGE_SIZE:
            message = (
                f"page_size must be between 1 and {MAXIMUM_SEARCH_PAGE_SIZE}"
            )
            raise ValueError(message)
        object.__setattr__(self, "query", normalized_query)


@dataclass(frozen=True, slots=True)
class SaleSearchResult:
    """One lightweight table projection from the local database."""

    observation_id: int
    external_item_id: str
    title: str
    sold_price: Money
    shipping_price: Money | None
    sold_at: datetime
    condition: ItemCondition | None
    listing_format: ListingFormat | None
    classification: ClassificationDecision

    @property
    def total_price(self) -> Money:
        """Return sold price plus known shipping."""
        shipping_minor = (
            self.shipping_price.minor_units if self.shipping_price is not None else 0
        )
        return Money(
            minor_units=self.sold_price.minor_units + shipping_minor,
            currency=self.sold_price.currency,
        )


@dataclass(frozen=True, slots=True)
class SaleSearchPage:
    """One keyset-paginated local result page."""

    items: tuple[SaleSearchResult, ...]
    next_cursor: SearchCursor | None

    @property
    def has_more(self) -> bool:
        """Return whether another page can be requested."""
        return self.next_cursor is not None


@dataclass(frozen=True, slots=True)
class RecentSearch:
    """A normalized query and its local usage metadata."""

    query: str
    last_used_at: datetime
    use_count: int
