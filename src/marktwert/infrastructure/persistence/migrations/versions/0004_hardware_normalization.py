"""Persist normalized hardware identity and extend FTS.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add normalized hardware attributes and rebuild the FTS index."""
    op.execute("DROP TRIGGER sale_observations_fts_update")
    op.execute("DROP TRIGGER sale_observations_fts_delete")
    op.execute("DROP TRIGGER sale_observations_fts_insert")
    op.execute("DROP TABLE sale_observations_fts")
    with op.batch_alter_table("sale_observations") as batch_op:
        batch_op.add_column(sa.Column("normalized_title", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("chipset", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("ram_capacity_gb", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("clock_speed_mhz", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("socket", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("revision", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("memory_size_gb", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("storage_size_gb", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("normalization_confidence", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("normalization_version", sa.String(64), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "normalization_evidence",
                sa.JSON(),
                server_default=sa.text("'[]'"),
                nullable=False,
            )
        )
    _create_fts()


def downgrade() -> None:
    """Remove normalized hardware attributes and restore the prior FTS index."""
    op.execute("DROP TRIGGER sale_observations_fts_update")
    op.execute("DROP TRIGGER sale_observations_fts_delete")
    op.execute("DROP TRIGGER sale_observations_fts_insert")
    op.execute("DROP TABLE sale_observations_fts")
    with op.batch_alter_table("sale_observations") as batch_op:
        batch_op.drop_column("normalization_evidence")
        batch_op.drop_column("normalization_version")
        batch_op.drop_column("normalization_confidence")
        batch_op.drop_column("storage_size_gb")
        batch_op.drop_column("memory_size_gb")
        batch_op.drop_column("revision")
        batch_op.drop_column("socket")
        batch_op.drop_column("clock_speed_mhz")
        batch_op.drop_column("ram_capacity_gb")
        batch_op.drop_column("chipset")
        batch_op.drop_column("normalized_title")
    op.execute(
        """
        CREATE VIRTUAL TABLE sale_observations_fts USING fts5(
            title, brand, model, part_number,
            content='sale_observations',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    _create_triggers(include_normalized_title=False)
    op.execute(
        "INSERT INTO sale_observations_fts(sale_observations_fts) "
        "VALUES('rebuild')"
    )


def _create_fts() -> None:
    op.execute(
        """
        CREATE VIRTUAL TABLE sale_observations_fts USING fts5(
            title, normalized_title, brand, model, part_number,
            content='sale_observations',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    _create_triggers(include_normalized_title=True)
    op.execute(
        "INSERT INTO sale_observations_fts(sale_observations_fts) "
        "VALUES('rebuild')"
    )


def _create_triggers(*, include_normalized_title: bool) -> None:
    columns = (
        "title, normalized_title, brand, model, part_number"
        if include_normalized_title
        else "title, brand, model, part_number"
    )
    new_values = ", ".join(f"new.{column.strip()}" for column in columns.split(","))
    old_values = ", ".join(f"old.{column.strip()}" for column in columns.split(","))
    op.execute(
        f"""
        CREATE TRIGGER sale_observations_fts_insert
        AFTER INSERT ON sale_observations BEGIN
            INSERT INTO sale_observations_fts(rowid, {columns})
            VALUES (new.id, {new_values});
        END
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER sale_observations_fts_delete
        AFTER DELETE ON sale_observations BEGIN
            INSERT INTO sale_observations_fts(
                sale_observations_fts, rowid, {columns}
            ) VALUES ('delete', old.id, {old_values});
        END
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER sale_observations_fts_update
        AFTER UPDATE OF {columns} ON sale_observations BEGIN
            INSERT INTO sale_observations_fts(
                sale_observations_fts, rowid, {columns}
            ) VALUES ('delete', old.id, {old_values});
            INSERT INTO sale_observations_fts(rowid, {columns})
            VALUES (new.id, {new_values});
        END
        """
    )
