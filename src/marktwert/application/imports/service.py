"""Transactional completed-sales file import orchestration."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from marktwert.application.imports.mapping import RowValidationError, SalesRowMapper
from marktwert.application.imports.models import (
    MAXIMUM_REPORTED_ISSUES,
    ImportIssue,
    ImportIssueCode,
    ImportPreview,
    ImportPreviewRow,
    ImportProgress,
    ImportReport,
    ImportSalesFile,
    SalesFileError,
)
from marktwert.application.imports.ports import (
    CancellationToken,
    NeverCancelled,
    NullProgressReporter,
    ProgressReporter,
    SalesFileReaderFactory,
)
from marktwert.application.ports import UnitOfWorkFactory
from marktwert.domain.normalization import HardwareTitleNormalizer
from marktwert.domain.sales import (
    ClassificationDecision,
    ClassificationResult,
    ListingClassificationPolicy,
    SaleObservation,
    TrackedProduct,
)

MAXIMUM_PREVIEW_ROWS = 100


@dataclass(frozen=True, slots=True)
class _PreparedRow:
    observation: SaleObservation
    classification: ClassificationResult


@dataclass(slots=True)
class _ImportState:
    processed_rows: int = 0
    created_observations: int = 0
    enriched_observations: int = 0
    duplicate_observations: int = 0
    accepted_rows: int = 0
    excluded_rows: int = 0
    review_rows: int = 0
    invalid_rows: int = 0
    committed_batches: int = 0
    cancelled: bool = False
    issues: list[ImportIssue] = field(default_factory=list)
    suppressed_issue_count: int = 0

    def add_issue(self, issue: ImportIssue) -> None:
        """Retain a bounded issue sample while counting every issue."""
        if len(self.issues) < MAXIMUM_REPORTED_ISSUES:
            self.issues.append(issue)
        else:
            self.suppressed_issue_count += 1

    def to_report(self) -> ImportReport:
        """Create an immutable final report."""
        return ImportReport(
            processed_rows=self.processed_rows,
            created_observations=self.created_observations,
            enriched_observations=self.enriched_observations,
            duplicate_observations=self.duplicate_observations,
            accepted_rows=self.accepted_rows,
            excluded_rows=self.excluded_rows,
            review_rows=self.review_rows,
            invalid_rows=self.invalid_rows,
            committed_batches=self.committed_batches,
            cancelled=self.cancelled,
            issues=tuple(self.issues),
            suppressed_issue_count=self.suppressed_issue_count,
        )


class ImportCompletedSalesService:
    """Validate, classify, and durably import completed-sale rows."""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        reader_factory: SalesFileReaderFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        normalizer: HardwareTitleNormalizer | None = None,
    ) -> None:
        """Initialize the use case with infrastructure ports."""
        self._unit_of_work_factory = unit_of_work_factory
        self._reader_factory = reader_factory
        self._clock = clock or _utc_now
        self._normalizer = normalizer or HardwareTitleNormalizer()
        self._classification_policy = ListingClassificationPolicy()
        self._custom_only_policy = ListingClassificationPolicy(
            faulty_terms=(),
            empty_box_terms=(),
            accessory_terms=(),
            replacement_part_terms=(),
            ambiguous_terms=(),
        )

    def preview(
        self,
        command: ImportSalesFile,
        *,
        limit: int = 25,
    ) -> ImportPreview:
        """Validate and classify a bounded preview without writing data."""
        if not 1 <= limit <= MAXIMUM_PREVIEW_ROWS:
            message = f"preview limit must be between 1 and {MAXIMUM_PREVIEW_ROWS}"
            raise ValueError(message)
        product = self._load_product(command)
        mapper = SalesRowMapper(command.default_timezone)
        acquired_at = self._clock()
        if acquired_at.tzinfo is None:
            message = "import clock must return a timezone-aware timestamp"
            raise ValueError(message)

        preview_rows: list[ImportPreviewRow] = []
        issues: list[ImportIssue] = []
        has_more = False
        inspected_rows = 0
        try:
            reader = self._reader_factory.create(command.path)
            schema_checked = False
            for row in reader.read_rows(command.path.resolve()):
                if inspected_rows >= limit:
                    has_more = True
                    break
                if not schema_checked:
                    missing_fields = mapper.missing_required_fields(row.values.keys())
                    if missing_fields:
                        return ImportPreview(
                            rows=(),
                            issues=(
                                ImportIssue(
                                    row_number=None,
                                    code=ImportIssueCode.MISSING_REQUIRED_COLUMN,
                                    message=(
                                        "missing required columns: "
                                        + ", ".join(missing_fields)
                                    ),
                                ),
                            ),
                            has_more=False,
                        )
                    schema_checked = True
                inspected_rows += 1
                try:
                    observation = mapper.map(
                        row,
                        source=command.source,
                        acquired_at=acquired_at,
                    )
                    observation = self._normalize_observation(observation)
                except RowValidationError as error:
                    issues.append(
                        ImportIssue(
                            row_number=row.row_number,
                            code=error.code,
                            message=str(error),
                        )
                    )
                    continue
                preview_rows.append(
                    ImportPreviewRow(
                        row_number=row.row_number,
                        external_item_id=observation.external_item_id,
                        title=observation.title,
                        total_price=observation.total_price,
                        sold_at=observation.sold_at,
                        classification=self._classify(product, observation.title),
                    )
                )
        except SalesFileError as error:
            issues.append(
                ImportIssue(
                    row_number=None,
                    code=ImportIssueCode.FILE_REJECTED,
                    message=str(error),
                )
            )
        if inspected_rows == 0 and not issues:
            issues.append(
                ImportIssue(
                    row_number=None,
                    code=ImportIssueCode.EMPTY_ROW,
                    message="import file contains no data rows",
                )
            )
        return ImportPreview(
            rows=tuple(preview_rows),
            issues=tuple(issues),
            has_more=has_more,
        )

    def execute(
        self,
        command: ImportSalesFile,
        *,
        cancellation: CancellationToken | None = None,
        progress: ProgressReporter | None = None,
    ) -> ImportReport:
        """Execute one bounded, resumable file import."""
        cancellation = cancellation or NeverCancelled()
        progress = progress or NullProgressReporter()
        product = self._load_product(command)
        mapper = SalesRowMapper(command.default_timezone)
        state = _ImportState()
        pending: list[_PreparedRow] = []
        acquired_at = self._clock()
        if acquired_at.tzinfo is None:
            message = "import clock must return a timezone-aware timestamp"
            raise ValueError(message)

        try:
            reader = self._reader_factory.create(command.path)
            rows = reader.read_rows(command.path.resolve())
            schema_checked = False
            for row in rows:
                if cancellation.is_cancelled:
                    state.cancelled = True
                    break
                if not schema_checked:
                    missing_fields = mapper.missing_required_fields(row.values.keys())
                    if missing_fields:
                        state.add_issue(
                            ImportIssue(
                                row_number=None,
                                code=ImportIssueCode.MISSING_REQUIRED_COLUMN,
                                message=(
                                    "missing required columns: "
                                    + ", ".join(missing_fields)
                                ),
                            )
                        )
                        return state.to_report()
                    schema_checked = True

                state.processed_rows += 1
                try:
                    observation = mapper.map(
                        row,
                        source=command.source,
                        acquired_at=acquired_at,
                    )
                    observation = self._normalize_observation(observation)
                except RowValidationError as error:
                    state.invalid_rows += 1
                    state.add_issue(
                        ImportIssue(
                            row_number=row.row_number,
                            code=error.code,
                            message=str(error),
                        )
                    )
                    continue

                pending.append(
                    _PreparedRow(
                        observation=observation,
                        classification=self._classify(product, observation.title),
                    )
                )
                if len(pending) >= command.batch_size:
                    self._commit_batch(command, pending, state)
                    pending.clear()
                    self._report_progress(state, progress)
        except SalesFileError as error:
            state.add_issue(
                ImportIssue(
                    row_number=None,
                    code=ImportIssueCode.FILE_REJECTED,
                    message=str(error),
                )
            )
            return state.to_report()

        if pending:
            self._commit_batch(command, pending, state)
            self._report_progress(state, progress)
        if state.processed_rows == 0 and not state.cancelled:
            state.add_issue(
                ImportIssue(
                    row_number=None,
                    code=ImportIssueCode.EMPTY_ROW,
                    message="import file contains no data rows",
                )
            )
        return state.to_report()

    def _load_product(self, command: ImportSalesFile) -> TrackedProduct:
        with self._unit_of_work_factory() as unit_of_work:
            product = unit_of_work.tracked_products.get(command.tracked_product_id)
        if product is None:
            message = "tracked product does not exist"
            raise ValueError(message)
        return product

    def _classify(self, product: TrackedProduct, title: str) -> ClassificationResult:
        criteria = product.criteria
        policy = (
            self._classification_policy
            if criteria.standalone_working_only
            else self._custom_only_policy
        )
        return policy.classify(
            title,
            required_terms=criteria.required_title_terms,
            additional_exclusion_terms=criteria.additional_exclusion_terms,
        )

    def _normalize_observation(
        self,
        observation: SaleObservation,
    ) -> SaleObservation:
        return replace(
            observation,
            product=self._normalizer.normalize(
                observation.title,
                source=observation.product,
            ),
        )

    def _commit_batch(
        self,
        command: ImportSalesFile,
        batch: list[_PreparedRow],
        state: _ImportState,
    ) -> None:
        batch_results: list[tuple[_PreparedRow, bool, bool]] = []
        with self._unit_of_work_factory() as unit_of_work:
            for prepared in batch:
                result = unit_of_work.sale_observations.upsert(
                    prepared.observation,
                    matched_product_id=command.tracked_product_id,
                    classification=prepared.classification,
                )
                batch_results.append(
                    (
                        prepared,
                        result.created,
                        bool(result.enriched_fields),
                    )
                )
            unit_of_work.commit()

        for prepared, created, enriched in batch_results:
            if created:
                state.created_observations += 1
            elif enriched:
                state.enriched_observations += 1
            else:
                state.duplicate_observations += 1
            if prepared.classification.decision is ClassificationDecision.ACCEPT:
                state.accepted_rows += 1
            elif prepared.classification.decision is ClassificationDecision.EXCLUDE:
                state.excluded_rows += 1
            else:
                state.review_rows += 1
        state.committed_batches += 1

    @staticmethod
    def _report_progress(
        state: _ImportState,
        reporter: ProgressReporter,
    ) -> None:
        reporter.report(
            ImportProgress(
                processed_rows=state.processed_rows,
                stored_rows=(
                    state.accepted_rows + state.excluded_rows + state.review_rows
                ),
                invalid_rows=state.invalid_rows,
            )
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)
