"""Ports used by the completed-sales import application service."""

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from marktwert.application.imports.models import ImportProgress, RawSalesRow


class SalesFileReader(Protocol):
    """Stream normalized rows from a supported tabular sales file."""

    def read_rows(self, path: Path) -> Iterator[RawSalesRow]:
        """Yield rows without loading the complete file into memory."""


class SalesFileReaderFactory(Protocol):
    """Select a reader for a validated file type."""

    def create(self, path: Path) -> SalesFileReader:
        """Return a reader for the supplied path."""


class CancellationToken(Protocol):
    """Expose cooperative cancellation without depending on Qt."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether the running import should stop."""


class ProgressReporter(Protocol):
    """Receive progress only after durable batch commits."""

    def report(self, progress: ImportProgress) -> None:
        """Publish current durable import counters."""


class NeverCancelled:
    """Default cancellation token for uninterrupted imports."""

    @property
    def is_cancelled(self) -> bool:
        """Always allow the import to continue."""
        return False


class NullProgressReporter:
    """Default reporter that intentionally discards progress."""

    def report(self, progress: ImportProgress) -> None:
        """Accept progress without side effects."""
        del progress
