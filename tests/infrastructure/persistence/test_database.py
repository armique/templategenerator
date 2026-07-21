"""Integration tests for SQLite configuration and migrations."""

from sqlalchemy import Engine, inspect, text


def test_migration_creates_expected_schema(sqlite_engine: Engine) -> None:
    inspector = inspect(sqlite_engine)

    assert {
        "alembic_version",
        "sale_observations",
        "source_revisions",
        "tracked_product_sales",
        "tracked_products",
    }.issubset(inspector.get_table_names())
    assert inspector.get_unique_constraints("sale_observations") == [
        {
            "name": "uq_sale_observations_source_item",
            "column_names": ["source", "external_item_id"],
        }
    ]


def test_sqlite_safety_pragmas_are_enabled(sqlite_engine: Engine) -> None:
    with sqlite_engine.connect() as connection:
        foreign_keys = connection.scalar(text("PRAGMA foreign_keys"))
        journal_mode = connection.scalar(text("PRAGMA journal_mode"))
        busy_timeout = connection.scalar(text("PRAGMA busy_timeout"))

    assert foreign_keys == 1
    assert str(journal_mode).lower() == "wal"
    assert busy_timeout == 5_000


def test_migration_is_idempotent(sqlite_engine: Engine) -> None:
    from marktwert.infrastructure.persistence import upgrade_database

    upgrade_database(sqlite_engine)

    with sqlite_engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert revision == "0001"
