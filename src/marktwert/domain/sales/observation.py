"""Completed-sale observation aggregate."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse

from marktwert.domain.money import Money
from marktwert.domain.sales.collection_profile import ItemCondition, ListingFormat


@dataclass(frozen=True, slots=True)
class SellerSnapshot:
    """Seller facts visible when a completed sale was collected."""

    name: str | None = None
    feedback_percentage: Decimal | None = None
    feedback_count: int | None = None

    def __post_init__(self) -> None:
        """Validate optional seller facts."""
        if self.feedback_percentage is not None and not (
            Decimal(0) <= self.feedback_percentage <= Decimal(100)
        ):
            message = "seller feedback percentage must be between 0 and 100"
            raise ValueError(message)
        if self.feedback_count is not None and self.feedback_count < 0:
            message = "seller feedback count cannot be negative"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ProductSnapshot:
    """Hardware identity facts extracted from the source listing."""

    brand: str | None = None
    model: str | None = None
    part_number: str | None = None
    category: str | None = None


@dataclass(frozen=True, slots=True)
class SaleObservation:
    """Immutable normalized facts for one marketplace completed sale."""

    source: str
    external_item_id: str
    title: str
    sold_price: Money
    sold_at: datetime
    acquired_at: datetime
    raw_record_hash: str
    shipping_price: Money | None = None
    condition: ItemCondition | None = None
    listing_format: ListingFormat | None = None
    best_offer: bool | None = None
    bid_count: int | None = None
    listing_url: str | None = None
    thumbnail_url: str | None = None
    location: str | None = None
    seller: SellerSnapshot = field(default_factory=SellerSnapshot)
    product: ProductSnapshot = field(default_factory=ProductSnapshot)

    def __post_init__(self) -> None:
        """Normalize text and enforce observation invariants."""
        for field_name in ("source", "external_item_id", "title", "raw_record_hash"):
            normalized = " ".join(str(getattr(self, field_name)).split())
            if not normalized:
                message = f"{field_name} cannot be empty"
                raise ValueError(message)
            object.__setattr__(self, field_name, normalized)

        if self.sold_price.minor_units < 0:
            message = "sold price cannot be negative"
            raise ValueError(message)
        if self.shipping_price is not None:
            if self.shipping_price.minor_units < 0:
                message = "shipping price cannot be negative"
                raise ValueError(message)
            if self.shipping_price.currency != self.sold_price.currency:
                message = "shipping and sold price currencies must match"
                raise ValueError(message)
        if self.bid_count is not None and self.bid_count < 0:
            message = "bid count cannot be negative"
            raise ValueError(message)
        if self.sold_at.tzinfo is None or self.acquired_at.tzinfo is None:
            message = "observation timestamps must be timezone-aware"
            raise ValueError(message)
        for url in (self.listing_url, self.thumbnail_url):
            if url is not None and urlparse(url).scheme not in {"http", "https"}:
                message = "listing URLs must use HTTP or HTTPS"
                raise ValueError(message)

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable source-level deduplication identity."""
        return self.source, self.external_item_id

    @property
    def total_price(self) -> Money:
        """Return sold price plus known shipping."""
        shipping_minor_units = (
            self.shipping_price.minor_units if self.shipping_price is not None else 0
        )
        return Money(
            minor_units=self.sold_price.minor_units + shipping_minor_units,
            currency=self.sold_price.currency,
        )

    def merge_missing(self, incoming: "SaleObservation") -> "SaleObservation":
        """Fill absent optional facts from another snapshot of the same sale."""
        if incoming.identity != self.identity:
            message = "cannot merge observations with different identities"
            raise ValueError(message)
        if incoming.sold_price.currency != self.sold_price.currency:
            message = "cannot merge observations with different currencies"
            raise ValueError(message)

        return replace(
            self,
            shipping_price=_prefer(self.shipping_price, incoming.shipping_price),
            condition=_prefer(self.condition, incoming.condition),
            listing_format=_prefer(self.listing_format, incoming.listing_format),
            best_offer=_prefer(self.best_offer, incoming.best_offer),
            bid_count=_prefer(self.bid_count, incoming.bid_count),
            listing_url=_prefer(self.listing_url, incoming.listing_url),
            thumbnail_url=_prefer(self.thumbnail_url, incoming.thumbnail_url),
            location=_prefer(self.location, incoming.location),
            seller=SellerSnapshot(
                name=_prefer(self.seller.name, incoming.seller.name),
                feedback_percentage=_prefer(
                    self.seller.feedback_percentage,
                    incoming.seller.feedback_percentage,
                ),
                feedback_count=_prefer(
                    self.seller.feedback_count,
                    incoming.seller.feedback_count,
                ),
            ),
            product=ProductSnapshot(
                brand=_prefer(self.product.brand, incoming.product.brand),
                model=_prefer(self.product.model, incoming.product.model),
                part_number=_prefer(
                    self.product.part_number,
                    incoming.product.part_number,
                ),
                category=_prefer(self.product.category, incoming.product.category),
            ),
        )


def _prefer[T](current: T | None, incoming: T | None) -> T | None:
    return current if current is not None else incoming
