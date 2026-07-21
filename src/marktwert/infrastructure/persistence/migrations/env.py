"""Alembic migration environment for the local SQLite database."""

from alembic import context
from sqlalchemy.engine import Connection


def run_migrations() -> None:
    """Run migrations on the connection supplied by the composition root."""
    connection = context.config.attributes.get("connection")
    if not isinstance(connection, Connection):
        message = "database migration requires an active SQLAlchemy connection"
        raise RuntimeError(message)

    context.configure(
        connection=connection,
        target_metadata=None,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations()
