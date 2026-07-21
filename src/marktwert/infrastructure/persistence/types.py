"""Database column types with explicit domain semantics."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """Persist UTC timestamps and always restore timezone awareness."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        """Convert an aware timestamp to naive UTC for SQLite."""
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            message = "UtcDateTime requires timezone-aware values"
            raise ValueError(message)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        """Restore persisted UTC values as timezone-aware timestamps."""
        del dialect
        return value.replace(tzinfo=UTC) if value is not None else None
