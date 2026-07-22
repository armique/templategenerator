"""SQLAlchemy repository implementations."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from marktwert.application.ports import ObservationUpsertResult
from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ClassificationDecision,
    ClassificationResult,
    CompletedSalesCriteria,
    ItemCondition,
    ListingFormat,
    PriceBasis,
    ProductSnapshot,
    SaleObservation,
    SellerSnapshot,
    TrackedProduct,
    TrackedProductId,
)
from marktwert.infrastructure.persistence.models import (
    SaleObservationRow,
    SourceRevisionRow,
    TrackedProductRow,
    TrackedProductSaleRow,
)

ACCEPTED_CLASSIFICATION = ClassificationResult(ClassificationDecision.ACCEPT)


class SqlAlchemyTrackedProductRepository:
    """Persist tracked-product profiles in a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one transaction-scoped session."""
        self._session = session

    def save(self, product: TrackedProduct) -> None:
        """Insert or update a tracked product."""
        product_id = str(product.id.value)
        row = self._session.get(TrackedProductRow, product_id)
        now = datetime.now(UTC)
        values = _tracked_product_values(product)
        if row is None:
            self._session.add(
                TrackedProductRow(
                    **values,
                    created_at=now,
                    updated_at=now,
                )
            )
            return

        for name, value in values.items():
            setattr(row, name, value)
        row.updated_at = now

    def get(self, product_id: TrackedProductId) -> TrackedProduct | None:
        """Return a tracked product by identity."""
        row = self._session.get(TrackedProductRow, str(product_id.value))
        return _row_to_tracked_product(row) if row is not None else None

    def list_all(self) -> tuple[TrackedProduct, ...]:
        """Return every tracked product in display order."""
        rows = self._session.scalars(
            select(TrackedProductRow).order_by(
                TrackedProductRow.name,
                TrackedProductRow.id,
            )
        )
        return tuple(_row_to_tracked_product(row) for row in rows)

    def remove(self, product_id: TrackedProductId) -> bool:
        """Remove a tracked product and report whether it existed."""
        row = self._session.get(TrackedProductRow, str(product_id.value))
        if row is None or row in self._session.deleted:
            return False
        self._session.delete(row)
        return True


class SqlAlchemySaleObservationRepository:
    """Persist and enrich deduplicated completed-sale observations."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one transaction-scoped session."""
        self._session = session

    def upsert(
        self,
        observation: SaleObservation,
        *,
        matched_product_id: TrackedProductId,
        classification: ClassificationResult = ACCEPTED_CLASSIFICATION,
    ) -> ObservationUpsertResult:
        """Insert, enrich, and associate one source observation."""
        product_id = str(matched_product_id.value)
        if self._session.get(TrackedProductRow, product_id) is None:
            message = "matched tracked product does not exist"
            raise ValueError(message)

        row = self._find_row(*observation.identity)
        created = row is None
        enriched_fields: tuple[str, ...] = ()
        if row is None:
            row = SaleObservationRow(**_observation_values(observation))
            self._session.add(row)
            self._session.flush()
        else:
            current = _row_to_observation(row)
            merged = current.merge_missing(observation)
            enriched_fields = _enriched_fields(current, merged)
            _apply_observation(row, merged)
            row.last_seen_at = max(row.last_seen_at, observation.acquired_at)

        revision_added = self._add_source_revision(row, observation)
        product_link_added, classification_updated = self._upsert_product_link(
            row,
            product_id=product_id,
            matched_at=observation.acquired_at,
            classification=classification,
        )
        return ObservationUpsertResult(
            created=created,
            enriched_fields=enriched_fields,
            source_revision_added=revision_added,
            product_link_added=product_link_added,
            classification_updated=classification_updated,
        )

    def get(
        self,
        source: str,
        external_item_id: str,
    ) -> SaleObservation | None:
        """Return one observation by stable source identity."""
        row = self._find_row(source, external_item_id)
        return _row_to_observation(row) if row is not None else None

    def list_for_product(
        self,
        product_id: TrackedProductId,
    ) -> tuple[SaleObservation, ...]:
        """Return observations associated with a tracked product."""
        rows = self._session.scalars(
            select(SaleObservationRow)
            .join(
                TrackedProductSaleRow,
                TrackedProductSaleRow.sale_observation_id == SaleObservationRow.id,
            )
            .where(
                TrackedProductSaleRow.tracked_product_id == str(product_id.value)
            )
            .order_by(SaleObservationRow.sold_at.desc(), SaleObservationRow.id)
        )
        return tuple(_row_to_observation(row) for row in rows)

    def _find_row(
        self,
        source: str,
        external_item_id: str,
    ) -> SaleObservationRow | None:
        return self._session.scalar(
            select(SaleObservationRow).where(
                SaleObservationRow.source == source,
                SaleObservationRow.external_item_id == external_item_id,
            )
        )

    def _add_source_revision(
        self,
        row: SaleObservationRow,
        observation: SaleObservation,
    ) -> bool:
        existing_id = self._session.scalar(
            select(SourceRevisionRow.id).where(
                SourceRevisionRow.sale_observation_id == row.id,
                SourceRevisionRow.raw_record_hash == observation.raw_record_hash,
            )
        )
        if existing_id is not None:
            return False
        self._session.add(
            SourceRevisionRow(
                sale_observation_id=row.id,
                raw_record_hash=observation.raw_record_hash,
                acquired_at=observation.acquired_at,
            )
        )
        return True

    def _upsert_product_link(
        self,
        row: SaleObservationRow,
        *,
        product_id: str,
        matched_at: datetime,
        classification: ClassificationResult,
    ) -> tuple[bool, bool]:
        existing_link = self._session.get(
            TrackedProductSaleRow,
            (product_id, row.id),
        )
        evidence = _classification_evidence_values(classification)
        if existing_link is not None:
            classification_updated = (
                existing_link.classification_decision != classification.decision.value
                or existing_link.classification_evidence != evidence
            )
            if classification_updated:
                existing_link.classification_decision = classification.decision.value
                existing_link.classification_evidence = evidence
            return False, classification_updated
        self._session.add(
            TrackedProductSaleRow(
                tracked_product_id=product_id,
                sale_observation_id=row.id,
                matched_at=matched_at,
                classification_decision=classification.decision.value,
                classification_evidence=evidence,
            )
        )
        return True, False


def _tracked_product_values(product: TrackedProduct) -> dict[str, object]:
    criteria = product.criteria
    return {
        "id": str(product.id.value),
        "name": product.name,
        "enabled": product.enabled,
        "query": criteria.query,
        "category_id": criteria.category_id,
        "brand": criteria.brand,
        "minimum_price_minor": (
            criteria.minimum_price.minor_units
            if criteria.minimum_price is not None
            else None
        ),
        "maximum_price_minor": (
            criteria.maximum_price.minor_units
            if criteria.maximum_price is not None
            else None
        ),
        "price_basis": criteria.price_basis.value,
        "conditions": sorted(condition.value for condition in criteria.conditions),
        "listing_formats": sorted(
            listing_format.value for listing_format in criteria.listing_formats
        ),
        "lookback_days": criteria.lookback_days,
        "marketplace_country": criteria.marketplace_country,
        "currency": criteria.currency,
        "standalone_working_only": criteria.standalone_working_only,
        "required_title_terms": list(criteria.required_title_terms),
        "additional_exclusion_terms": list(criteria.additional_exclusion_terms),
    }


def _row_to_tracked_product(row: TrackedProductRow) -> TrackedProduct:
    minimum_price = (
        Money(row.minimum_price_minor, row.currency)
        if row.minimum_price_minor is not None
        else None
    )
    maximum_price = (
        Money(row.maximum_price_minor, row.currency)
        if row.maximum_price_minor is not None
        else None
    )
    return TrackedProduct(
        id=TrackedProductId(UUID(row.id)),
        name=row.name,
        enabled=row.enabled,
        criteria=CompletedSalesCriteria(
            query=row.query,
            category_id=row.category_id,
            brand=row.brand,
            minimum_price=minimum_price,
            maximum_price=maximum_price,
            price_basis=PriceBasis(row.price_basis),
            conditions=frozenset(ItemCondition(value) for value in row.conditions),
            listing_formats=frozenset(
                ListingFormat(value) for value in row.listing_formats
            ),
            lookback_days=row.lookback_days,
            marketplace_country=row.marketplace_country,
            currency=row.currency,
            standalone_working_only=row.standalone_working_only,
            required_title_terms=tuple(row.required_title_terms),
            additional_exclusion_terms=tuple(row.additional_exclusion_terms),
        ),
    )


def _observation_values(observation: SaleObservation) -> dict[str, object]:
    return {
        "source": observation.source,
        "external_item_id": observation.external_item_id,
        "title": observation.title,
        "sold_price_minor": observation.sold_price.minor_units,
        "shipping_price_minor": (
            observation.shipping_price.minor_units
            if observation.shipping_price is not None
            else None
        ),
        "currency": observation.sold_price.currency,
        "sold_at": observation.sold_at,
        "acquired_at": observation.acquired_at,
        "last_seen_at": observation.acquired_at,
        "raw_record_hash": observation.raw_record_hash,
        "condition": (
            observation.condition.value if observation.condition is not None else None
        ),
        "listing_format": (
            observation.listing_format.value
            if observation.listing_format is not None
            else None
        ),
        "best_offer": observation.best_offer,
        "bid_count": observation.bid_count,
        "listing_url": observation.listing_url,
        "thumbnail_url": observation.thumbnail_url,
        "location": observation.location,
        "seller_name": observation.seller.name,
        "seller_feedback_percentage": observation.seller.feedback_percentage,
        "seller_feedback_count": observation.seller.feedback_count,
        "normalized_title": observation.product.normalized_title,
        "brand": observation.product.brand,
        "model": observation.product.model,
        "part_number": observation.product.part_number,
        "category": observation.product.category,
        "chipset": observation.product.chipset,
        "ram_capacity_gb": observation.product.ram_capacity_gb,
        "clock_speed_mhz": observation.product.clock_speed_mhz,
        "socket": observation.product.socket,
        "revision": observation.product.revision,
        "memory_size_gb": observation.product.memory_size_gb,
        "storage_size_gb": observation.product.storage_size_gb,
        "normalization_confidence": observation.product.normalization_confidence,
        "normalization_version": observation.product.normalization_version,
        "normalization_evidence": list(
            observation.product.normalization_evidence
        ),
    }


def _apply_observation(
    row: SaleObservationRow,
    observation: SaleObservation,
) -> None:
    values = _observation_values(observation)
    values.pop("last_seen_at")
    for name, value in values.items():
        setattr(row, name, value)


def _row_to_observation(row: SaleObservationRow) -> SaleObservation:
    return SaleObservation(
        source=row.source,
        external_item_id=row.external_item_id,
        title=row.title,
        sold_price=Money(row.sold_price_minor, row.currency),
        shipping_price=(
            Money(row.shipping_price_minor, row.currency)
            if row.shipping_price_minor is not None
            else None
        ),
        sold_at=row.sold_at,
        acquired_at=row.acquired_at,
        raw_record_hash=row.raw_record_hash,
        condition=ItemCondition(row.condition) if row.condition is not None else None,
        listing_format=(
            ListingFormat(row.listing_format)
            if row.listing_format is not None
            else None
        ),
        best_offer=row.best_offer,
        bid_count=row.bid_count,
        listing_url=row.listing_url,
        thumbnail_url=row.thumbnail_url,
        location=row.location,
        seller=SellerSnapshot(
            name=row.seller_name,
            feedback_percentage=row.seller_feedback_percentage,
            feedback_count=row.seller_feedback_count,
        ),
        product=ProductSnapshot(
            normalized_title=row.normalized_title,
            brand=row.brand,
            model=row.model,
            part_number=row.part_number,
            category=row.category,
            chipset=row.chipset,
            ram_capacity_gb=row.ram_capacity_gb,
            clock_speed_mhz=row.clock_speed_mhz,
            socket=row.socket,
            revision=row.revision,
            memory_size_gb=row.memory_size_gb,
            storage_size_gb=row.storage_size_gb,
            normalization_confidence=row.normalization_confidence,
            normalization_version=row.normalization_version,
            normalization_evidence=tuple(row.normalization_evidence),
        ),
    )


def _enriched_fields(
    previous: SaleObservation,
    merged: SaleObservation,
) -> tuple[str, ...]:
    field_values = (
        ("shipping_price", previous.shipping_price, merged.shipping_price),
        ("condition", previous.condition, merged.condition),
        ("listing_format", previous.listing_format, merged.listing_format),
        ("best_offer", previous.best_offer, merged.best_offer),
        ("bid_count", previous.bid_count, merged.bid_count),
        ("listing_url", previous.listing_url, merged.listing_url),
        ("thumbnail_url", previous.thumbnail_url, merged.thumbnail_url),
        ("location", previous.location, merged.location),
        ("seller", previous.seller, merged.seller),
        ("product", previous.product, merged.product),
    )
    return tuple(
        field_name
        for field_name, previous_value, merged_value in field_values
        if previous_value != merged_value
    )


def _classification_evidence_values(
    classification: ClassificationResult,
) -> list[dict[str, str]]:
    return [
        {
            "reason": item.reason.value,
            "matched_term": item.matched_term,
        }
        for item in classification.evidence
    ]
