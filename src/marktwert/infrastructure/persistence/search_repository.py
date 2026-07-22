"""SQLAlchemy local completed-sales search implementation."""

import re
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import (
    String,
    and_,
    column,
    func,
    or_,
    select,
    table,
    text,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from marktwert.application.search import (
    RecentSearch,
    SaleSearchPage,
    SaleSearchResult,
    SearchCursor,
    SearchSales,
)
from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ClassificationDecision,
    ItemCondition,
    ListingFormat,
)
from marktwert.infrastructure.persistence.models import (
    RecentSearchRow,
    SaleObservationRow,
    TrackedProductSaleRow,
)

MAXIMUM_FTS_TOKENS = 12
MAXIMUM_FTS_TOKEN_LENGTH = 64
MAXIMUM_RECENT_SEARCHES = 50
SALE_OBSERVATIONS_FTS = table(
    "sale_observations_fts",
    column("rowid"),
    column("title", String),
    column("brand", String),
    column("model", String),
    column("part_number", String),
)


class SqlAlchemySaleSearchRepository:
    """Search indexed local sales and maintain recent query history."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one transaction-scoped session."""
        self._session = session

    def search(self, request: SearchSales) -> SaleSearchPage:
        """Return one filtered keyset-paginated local result page."""
        fts_query = _build_fts_query(request.query)
        if request.query and fts_query is None:
            return SaleSearchPage(items=(), next_cursor=None)

        classification = (
            select(
                TrackedProductSaleRow.sale_observation_id.label("observation_id"),
                func.min(TrackedProductSaleRow.classification_decision).label(
                    "classification"
                ),
            )
            .where(
                TrackedProductSaleRow.classification_decision.in_(
                    decision.value for decision in request.filters.classifications
                )
            )
            .group_by(TrackedProductSaleRow.sale_observation_id)
        )
        if request.filters.tracked_product_id is not None:
            classification = classification.where(
                TrackedProductSaleRow.tracked_product_id
                == str(request.filters.tracked_product_id.value)
            )
        classification_subquery = classification.subquery()

        statement = (
            select(
                SaleObservationRow.id.label("observation_id"),
                SaleObservationRow.external_item_id,
                SaleObservationRow.title,
                SaleObservationRow.sold_price_minor,
                SaleObservationRow.shipping_price_minor,
                SaleObservationRow.currency,
                SaleObservationRow.sold_at,
                SaleObservationRow.condition,
                SaleObservationRow.listing_format,
                classification_subquery.c.classification,
            )
            .join(
                classification_subquery,
                classification_subquery.c.observation_id == SaleObservationRow.id,
            )
            .order_by(SaleObservationRow.sold_at.desc(), SaleObservationRow.id.desc())
            .limit(request.page_size + 1)
        )
        if fts_query is not None:
            statement = statement.join(
                SALE_OBSERVATIONS_FTS,
                SALE_OBSERVATIONS_FTS.c.rowid == SaleObservationRow.id,
            ).where(text("sale_observations_fts MATCH :fts_query"))
            statement = statement.params(fts_query=fts_query)

        filter_conditions = _filter_conditions(request)
        if filter_conditions:
            statement = statement.where(*filter_conditions)
        rows = self._session.execute(statement).mappings().all()
        has_more = len(rows) > request.page_size
        page_rows = rows[: request.page_size]
        items = tuple(_mapping_to_result(row) for row in page_rows)
        next_cursor = (
            SearchCursor(
                sold_at=items[-1].sold_at,
                observation_id=items[-1].observation_id,
            )
            if has_more and items
            else None
        )
        return SaleSearchPage(items=items, next_cursor=next_cursor)

    def record_recent(self, query: str) -> None:
        """Record a successful non-empty query."""
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return
        now = datetime.now(UTC)
        statement = sqlite_insert(RecentSearchRow).values(
            query=normalized_query,
            last_used_at=now,
            use_count=1,
        )
        self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[RecentSearchRow.query],
                set_={
                    "last_used_at": now,
                    "use_count": RecentSearchRow.use_count + 1,
                },
            )
        )

    def list_recent(self, *, limit: int = 10) -> tuple[RecentSearch, ...]:
        """Return most recently used local queries."""
        if not 1 <= limit <= MAXIMUM_RECENT_SEARCHES:
            message = (
                f"recent search limit must be between 1 and {MAXIMUM_RECENT_SEARCHES}"
            )
            raise ValueError(message)
        rows = self._session.scalars(
            select(RecentSearchRow)
            .order_by(RecentSearchRow.last_used_at.desc(), RecentSearchRow.query)
            .limit(limit)
        )
        return tuple(
            RecentSearch(
                query=row.query,
                last_used_at=row.last_used_at,
                use_count=row.use_count,
            )
            for row in rows
        )


def _build_fts_query(query: str) -> str | None:
    if not query:
        return None
    tokens = re.findall(r"\w+", query.casefold(), flags=re.UNICODE)
    bounded_tokens = [
        token[:MAXIMUM_FTS_TOKEN_LENGTH]
        for token in tokens[:MAXIMUM_FTS_TOKENS]
        if token
    ]
    if not bounded_tokens:
        return None
    return " AND ".join(f'"{token}"*' for token in bounded_tokens)


def _filter_conditions(request: SearchSales) -> list[ColumnElement[bool]]:
    filters = request.filters
    conditions: list[ColumnElement[bool]] = []
    total_price = SaleObservationRow.sold_price_minor + func.coalesce(
        SaleObservationRow.shipping_price_minor,
        0,
    )
    if filters.minimum_price is not None:
        conditions.extend(
            (
                SaleObservationRow.currency == filters.minimum_price.currency,
                total_price >= filters.minimum_price.minor_units,
            )
        )
    if filters.maximum_price is not None:
        conditions.extend(
            (
                SaleObservationRow.currency == filters.maximum_price.currency,
                total_price <= filters.maximum_price.minor_units,
            )
        )
    if filters.sold_from is not None:
        conditions.append(SaleObservationRow.sold_at >= filters.sold_from)
    if filters.sold_to is not None:
        conditions.append(SaleObservationRow.sold_at <= filters.sold_to)
    if filters.conditions:
        conditions.append(
            SaleObservationRow.condition.in_(
                condition.value for condition in filters.conditions
            )
        )
    if filters.listing_formats:
        conditions.append(
            SaleObservationRow.listing_format.in_(
                listing_format.value for listing_format in filters.listing_formats
            )
        )
    if request.cursor is not None:
        conditions.append(
            or_(
                SaleObservationRow.sold_at < request.cursor.sold_at,
                and_(
                    SaleObservationRow.sold_at == request.cursor.sold_at,
                    SaleObservationRow.id < request.cursor.observation_id,
                ),
            )
        )
    return conditions


def _mapping_to_result(mapping: RowMapping) -> SaleSearchResult:
    currency = cast(str, mapping["currency"])
    shipping_minor = cast(int | None, mapping["shipping_price_minor"])
    condition = cast(str | None, mapping["condition"])
    listing_format = cast(str | None, mapping["listing_format"])
    return SaleSearchResult(
        observation_id=cast(int, mapping["observation_id"]),
        external_item_id=cast(str, mapping["external_item_id"]),
        title=cast(str, mapping["title"]),
        sold_price=Money(cast(int, mapping["sold_price_minor"]), currency),
        shipping_price=(
            Money(shipping_minor, currency) if shipping_minor is not None else None
        ),
        sold_at=cast(datetime, mapping["sold_at"]),
        condition=ItemCondition(condition) if condition is not None else None,
        listing_format=(
            ListingFormat(listing_format) if listing_format is not None else None
        ),
        classification=ClassificationDecision(cast(str, mapping["classification"])),
    )
