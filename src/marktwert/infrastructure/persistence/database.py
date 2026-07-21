"""SQLite engine configuration and schema migration."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry

SQLITE_BUSY_TIMEOUT_MILLISECONDS = 5_000


def create_sqlite_engine(
    database_path: Path,
    *,
    echo: bool = False,
) -> Engine:
    """Create an SQLite engine with safe desktop-application pragmas."""
    resolved_path = database_path.expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite+pysqlite:///{resolved_path.as_posix()}",
        echo=echo,
        future=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure_connection(
        dbapi_connection: DBAPIConnection,
        connection_record: ConnectionPoolEntry,
    ) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(
                f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MILLISECONDS}"
            )
            cursor.execute("PRAGMA journal_mode = WAL")
        finally:
            cursor.close()

    return engine


def upgrade_database(engine: Engine) -> None:
    """Upgrade the database transactionally to the latest known schema."""
    migrations_path = Path(__file__).with_name("migrations")
    config = Config()
    config.set_main_option("script_location", str(migrations_path))
    with engine.begin() as connection:
        _run_upgrade(config, connection)


def _run_upgrade(config: Config, connection: Connection) -> None:
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
