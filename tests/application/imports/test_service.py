"""Integration tests for transactional completed-sales imports."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from marktwert.application.imports import (
    ImportCompletedSalesService,
    ImportIssueCode,
    ImportProgress,
    ImportSalesFile,
)
from marktwert.domain.sales import CompletedSalesCriteria, TrackedProduct
from marktwert.infrastructure.imports import TabularSalesFileReaderFactory
from marktwert.infrastructure.persistence import (
    create_sqlite_engine,
    upgrade_database,
)
from marktwert.infrastructure.persistence.models import TrackedProductSaleRow
from marktwert.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

ACQUIRED_AT = datetime(2026, 7, 22, 12, tzinfo=UTC)


@dataclass(slots=True)
class RecordingProgress:
    """Collect progress updates for assertions."""

    updates: list[ImportProgress] = field(default_factory=list)

    def report(self, progress: ImportProgress) -> None:
        """Record a durable progress update."""
        self.updates.append(progress)


@dataclass(slots=True)
class CancelAfterChecks:
    """Request cancellation after a fixed number of row checks."""

    allowed_checks: int
    checks: int = 0

    @property
    def is_cancelled(self) -> bool:
        """Become cancelled after the configured checks."""
        self.checks += 1
        return self.checks > self.allowed_checks


def create_context(
    tmp_path: Path,
) -> tuple[Engine, TrackedProduct, ImportCompletedSalesService]:
    """Create a migrated database, tracked product, and import service."""
    engine = create_sqlite_engine(tmp_path / "imports.db")
    upgrade_database(engine)
    factory = SqlAlchemyUnitOfWork.factory_for(engine)
    product = TrackedProduct.create(
        name="RTX 3070",
        criteria=CompletedSalesCriteria(query="RTX 3070"),
    )
    with factory() as unit_of_work:
        unit_of_work.tracked_products.save(product)
        unit_of_work.commit()
    service = ImportCompletedSalesService(
        factory,
        TabularSalesFileReaderFactory(),
        clock=lambda: ACQUIRED_AT,
    )
    return engine, product, service


def write_mixed_sales_file(path: Path) -> None:
    """Write accepted, excluded, review, invalid, and duplicate rows."""
    path.write_text(
        "item_id;title;sold_price;shipping_price;sold_at;condition\n"
        "1;RTX 3070 Gaming OC 8 GB;300,00;6,99;21.07.2026;Gebraucht\n"
        "2;RTX 3070 nur OVP;20,00;;20.07.2026;Gebraucht\n"
        "3;RTX 3070 ungeprüft;180,00;;19.07.2026;Gebraucht\n"
        "4;RTX 3070 ohne Preis;;;18.07.2026;Gebraucht\n"
        "1;RTX 3070 Gaming OC 8 GB;300,00;6,99;21.07.2026;Gebraucht\n",
        encoding="utf-8",
    )


def test_service_imports_classifies_quarantines_and_deduplicates(
    tmp_path: Path,
) -> None:
    engine, product, service = create_context(tmp_path)
    path = tmp_path / "sales.csv"
    write_mixed_sales_file(path)
    progress = RecordingProgress()

    report = service.execute(
        ImportSalesFile(
            path=path,
            source="manual_csv",
            tracked_product_id=product.id,
            batch_size=2,
        ),
        progress=progress,
    )

    assert report.processed_rows == 5
    assert report.created_observations == 3
    assert report.enriched_observations == 0
    assert report.duplicate_observations == 1
    assert report.accepted_rows == 2
    assert report.excluded_rows == 1
    assert report.review_rows == 1
    assert report.invalid_rows == 1
    assert report.committed_batches == 2
    assert report.cancelled is False
    assert report.issues[0].row_number == 5
    assert report.issues[0].code is ImportIssueCode.INVALID_VALUE
    assert len(progress.updates) == 2

    with Session(engine) as session:
        links = tuple(
            session.scalars(
                select(TrackedProductSaleRow).order_by(
                    TrackedProductSaleRow.sale_observation_id
                )
            )
        )
    assert [link.classification_decision for link in links] == [
        "accept",
        "exclude",
        "review",
    ]
    assert links[1].classification_evidence == [
        {"reason": "empty_box", "matched_term": "nur ovp"}
    ]
    factory = SqlAlchemyUnitOfWork.factory_for(engine)
    with factory() as unit_of_work:
        normalized = unit_of_work.sale_observations.get("manual_csv", "1")
    assert normalized is not None
    assert normalized.product.brand is None
    assert normalized.product.model == "RTX 3070"
    assert normalized.product.normalized_title == "RTX 3070 Gaming OC"
    engine.dispose()


def test_service_reimport_is_observation_idempotent(tmp_path: Path) -> None:
    engine, product, service = create_context(tmp_path)
    path = tmp_path / "sales.csv"
    write_mixed_sales_file(path)
    command = ImportSalesFile(
        path=path,
        source="manual_csv",
        tracked_product_id=product.id,
    )

    service.execute(command)
    second_report = service.execute(command)

    assert second_report.created_observations == 0
    assert second_report.duplicate_observations == 4
    engine.dispose()


def test_service_commits_pending_page_on_cancellation(tmp_path: Path) -> None:
    engine, product, service = create_context(tmp_path)
    path = tmp_path / "sales.csv"
    write_mixed_sales_file(path)

    report = service.execute(
        ImportSalesFile(
            path=path,
            source="manual_csv",
            tracked_product_id=product.id,
            batch_size=10,
        ),
        cancellation=CancelAfterChecks(allowed_checks=2),
    )

    assert report.cancelled is True
    assert report.processed_rows == 2
    assert report.created_observations == 2
    assert report.committed_batches == 1
    engine.dispose()


def test_service_reports_missing_required_columns(tmp_path: Path) -> None:
    engine, product, service = create_context(tmp_path)
    path = tmp_path / "sales.csv"
    path.write_text("item_id;title\n1;RTX 3070\n", encoding="utf-8")

    report = service.execute(
        ImportSalesFile(
            path=path,
            source="manual_csv",
            tracked_product_id=product.id,
        )
    )

    assert report.processed_rows == 0
    assert report.issues[0].code is ImportIssueCode.MISSING_REQUIRED_COLUMN
    assert "sold_at" in report.issues[0].message
    assert "sold_price" in report.issues[0].message
    engine.dispose()


def test_service_previews_without_persisting(tmp_path: Path) -> None:
    engine, product, service = create_context(tmp_path)
    path = tmp_path / "sales.csv"
    write_mixed_sales_file(path)
    command = ImportSalesFile(
        path=path,
        source="manual_csv",
        tracked_product_id=product.id,
    )

    preview = service.preview(command, limit=2)

    assert len(preview.rows) == 2
    assert preview.rows[0].total_price.minor_units == 30_699
    assert preview.rows[1].classification.decision.value == "exclude"
    assert preview.has_more is True
    with SqlAlchemyUnitOfWork.factory_for(engine)() as unit_of_work:
        assert unit_of_work.sale_observations.list_for_product(product.id) == ()
    engine.dispose()
