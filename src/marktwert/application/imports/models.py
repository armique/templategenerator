"""Typed commands and results for completed-sales file imports."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from marktwert.domain.money import Money
from marktwert.domain.sales import ClassificationResult, TrackedProductId

DEFAULT_IMPORT_BATCH_SIZE = 250
MAXIMUM_IMPORT_BATCH_SIZE = 2_000
MAXIMUM_REPORTED_ISSUES = 1_000


class SalesFileError(ValueError):
    """Report a file-level validation failure safe for user display."""


class ImportIssueCode(StrEnum):
    """Stable issue codes suitable for UI display and report exports."""

    MISSING_REQUIRED_COLUMN = "missing_required_column"
    INVALID_VALUE = "invalid_value"
    EMPTY_ROW = "empty_row"
    FILE_REJECTED = "file_rejected"


@dataclass(frozen=True, slots=True)
class ImportSalesFile:
    """Request a validated file import for one tracked product."""

    path: Path
    source: str
    tracked_product_id: TrackedProductId
    default_timezone: str = "Europe/Berlin"
    batch_size: int = DEFAULT_IMPORT_BATCH_SIZE

    def __post_init__(self) -> None:
        """Normalize command values and validate bounded batch processing."""
        normalized_source = " ".join(self.source.split())
        if not normalized_source:
            message = "import source cannot be empty"
            raise ValueError(message)
        if not 1 <= self.batch_size <= MAXIMUM_IMPORT_BATCH_SIZE:
            message = (
                f"batch_size must be between 1 and {MAXIMUM_IMPORT_BATCH_SIZE}"
            )
            raise ValueError(message)
        object.__setattr__(self, "path", self.path.expanduser())
        object.__setattr__(self, "source", normalized_source)


@dataclass(frozen=True, slots=True)
class RawSalesRow:
    """One source row with its user-visible row number."""

    row_number: int
    values: dict[str, object | None]


@dataclass(frozen=True, slots=True)
class ImportIssue:
    """A quarantined row or file issue."""

    row_number: int | None
    code: ImportIssueCode
    message: str


@dataclass(frozen=True, slots=True)
class ImportPreviewRow:
    """One normalized and classified row shown before persistence."""

    row_number: int
    external_item_id: str
    title: str
    total_price: Money
    sold_at: datetime
    classification: ClassificationResult


@dataclass(frozen=True, slots=True)
class ImportPreview:
    """Bounded file preview with validation issues and continuation state."""

    rows: tuple[ImportPreviewRow, ...]
    issues: tuple[ImportIssue, ...]
    has_more: bool


@dataclass(frozen=True, slots=True)
class ImportProgress:
    """Incremental counters emitted after each committed page."""

    processed_rows: int
    stored_rows: int
    invalid_rows: int


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Final durable and quarantined outcomes of an import operation."""

    processed_rows: int
    created_observations: int
    enriched_observations: int
    duplicate_observations: int
    accepted_rows: int
    excluded_rows: int
    review_rows: int
    invalid_rows: int
    committed_batches: int
    cancelled: bool
    issues: tuple[ImportIssue, ...] = ()
    suppressed_issue_count: int = 0

    @property
    def stored_rows(self) -> int:
        """Return the number of valid rows linked to the tracked product."""
        return self.accepted_rows + self.excluded_rows + self.review_rows
