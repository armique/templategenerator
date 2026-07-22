"""Add local full-text search and recent-query history.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create query history and a trigger-maintained FTS5 index."""
    op.create_table(
        "recent_searches",
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("query", name="pk_recent_searches"),
    )
    op.execute(
        """
        CREATE VIRTUAL TABLE sale_observations_fts USING fts5(
            title,
            brand,
            model,
            part_number,
            content='sale_observations',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER sale_observations_fts_insert
        AFTER INSERT ON sale_observations BEGIN
            INSERT INTO sale_observations_fts(
                rowid, title, brand, model, part_number
            ) VALUES (
                new.id, new.title, new.brand, new.model, new.part_number
            );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER sale_observations_fts_delete
        AFTER DELETE ON sale_observations BEGIN
            INSERT INTO sale_observations_fts(
                sale_observations_fts, rowid, title, brand, model, part_number
            ) VALUES (
                'delete', old.id, old.title, old.brand, old.model, old.part_number
            );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER sale_observations_fts_update
        AFTER UPDATE OF title, brand, model, part_number
        ON sale_observations BEGIN
            INSERT INTO sale_observations_fts(
                sale_observations_fts, rowid, title, brand, model, part_number
            ) VALUES (
                'delete', old.id, old.title, old.brand, old.model, old.part_number
            );
            INSERT INTO sale_observations_fts(
                rowid, title, brand, model, part_number
            ) VALUES (
                new.id, new.title, new.brand, new.model, new.part_number
            );
        END
        """
    )
    op.execute(
        "INSERT INTO sale_observations_fts(sale_observations_fts) VALUES('rebuild')"
    )


def downgrade() -> None:
    """Remove local full-text search and query history."""
    op.execute("DROP TRIGGER sale_observations_fts_update")
    op.execute("DROP TRIGGER sale_observations_fts_delete")
    op.execute("DROP TRIGGER sale_observations_fts_insert")
    op.execute("DROP TABLE sale_observations_fts")
    op.drop_table("recent_searches")
