"""SQLAlchemy accepted-sale projection repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from marktwert.application.analytics import SaleAnalyticsPoint
from marktwert.domain.sales import ClassificationDecision, TrackedProductId
from marktwert.infrastructure.persistence.models import (
    SaleObservationRow,
    TrackedProductSaleRow,
)


class SqlAlchemyMarketAnalyticsRepository:
    """Load bounded accepted-sale data without materializing aggregates."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one transaction-scoped session."""
        self._session = session

    def list_accepted(
        self,
        product_id: TrackedProductId,
        *,
        sold_from: datetime | None,
    ) -> tuple[SaleAnalyticsPoint, ...]:
        """Return accepted sales ordered chronologically."""
        statement = (
            select(
                SaleObservationRow.sold_at,
                SaleObservationRow.sold_price_minor,
                SaleObservationRow.shipping_price_minor,
                SaleObservationRow.currency,
            )
            .join(
                TrackedProductSaleRow,
                TrackedProductSaleRow.sale_observation_id == SaleObservationRow.id,
            )
            .where(
                TrackedProductSaleRow.tracked_product_id == str(product_id.value),
                TrackedProductSaleRow.classification_decision
                == ClassificationDecision.ACCEPT.value,
            )
            .order_by(SaleObservationRow.sold_at, SaleObservationRow.id)
        )
        if sold_from is not None:
            statement = statement.where(SaleObservationRow.sold_at >= sold_from)
        rows = self._session.execute(statement).tuples()
        return tuple(
            SaleAnalyticsPoint(
                sold_at=sold_at,
                sold_price_minor=sold_price_minor,
                shipping_price_minor=shipping_price_minor,
                currency=currency,
            )
            for sold_at, sold_price_minor, shipping_price_minor, currency in rows
        )
