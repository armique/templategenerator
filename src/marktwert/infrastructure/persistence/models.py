"""SQLAlchemy mappings for local application state."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from marktwert.infrastructure.persistence.types import UtcDateTime

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base mapping with deterministic constraint names."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TrackedProductRow(Base):
    """Persisted tracked-product profile."""

    __tablename__ = "tracked_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(32))
    brand: Mapped[str | None] = mapped_column(String(120))
    minimum_price_minor: Mapped[int | None] = mapped_column(BigInteger)
    maximum_price_minor: Mapped[int | None] = mapped_column(BigInteger)
    price_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    listing_formats: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    marketplace_country: Mapped[str] = mapped_column(String(2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    standalone_working_only: Mapped[bool] = mapped_column(Boolean, nullable=False)
    required_title_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    additional_exclusion_terms: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class SaleObservationRow(Base):
    """Persisted normalized completed-sale observation."""

    __tablename__ = "sale_observations"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_item_id",
            name="uq_sale_observations_source_item",
        ),
        Index("ix_sale_observations_sold_at", "sold_at"),
        Index("ix_sale_observations_product", "brand", "model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sold_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_price_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sold_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    raw_record_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    condition: Mapped[str | None] = mapped_column(String(32))
    listing_format: Mapped[str | None] = mapped_column(String(32))
    best_offer: Mapped[bool | None] = mapped_column(Boolean)
    bid_count: Mapped[int | None] = mapped_column(Integer)
    listing_url: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    seller_name: Mapped[str | None] = mapped_column(String(200))
    seller_feedback_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    seller_feedback_count: Mapped[int | None] = mapped_column(Integer)
    brand: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(200))
    part_number: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(200))


class SourceRevisionRow(Base):
    """Record each distinct source revision observed for a sold listing."""

    __tablename__ = "source_revisions"
    __table_args__ = (
        UniqueConstraint(
            "sale_observation_id",
            "raw_record_hash",
            name="uq_source_revisions_observation_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_observation_id: Mapped[int] = mapped_column(
        ForeignKey("sale_observations.id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_record_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class TrackedProductSaleRow(Base):
    """Associate one observation with every matching tracked product."""

    __tablename__ = "tracked_product_sales"

    tracked_product_id: Mapped[str] = mapped_column(
        ForeignKey("tracked_products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sale_observation_id: Mapped[int] = mapped_column(
        ForeignKey("sale_observations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    matched_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    classification_decision: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    classification_evidence: Mapped[list[dict[str, str]]] = mapped_column(
        JSON,
        nullable=False,
    )


class RecentSearchRow(Base):
    """Persist normalized local query usage."""

    __tablename__ = "recent_searches"

    query: Mapped[str] = mapped_column(String(200), primary_key=True)
    last_used_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False)


def model_metadata() -> MetaData:
    """Return schema metadata for migrations and integrity tooling."""
    return Base.metadata
