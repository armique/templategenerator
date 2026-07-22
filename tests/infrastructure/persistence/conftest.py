"""Fixtures for real SQLite persistence tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from marktwert.infrastructure.persistence import (
    create_sqlite_engine,
    upgrade_database,
)


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[Engine]:
    """Create and migrate an isolated file-backed SQLite database."""
    engine = create_sqlite_engine(tmp_path / "marktwert-test.db")
    upgrade_database(engine)
    try:
        yield engine
    finally:
        engine.dispose()
