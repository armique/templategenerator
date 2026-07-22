"""Store per-product sale classification.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add explainable classification to each product-sale association."""
    with op.batch_alter_table("tracked_product_sales") as batch_op:
        batch_op.add_column(
            sa.Column(
                "classification_decision",
                sa.String(length=16),
                server_default="accept",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "classification_evidence",
                sa.JSON(),
                server_default=sa.text("'[]'"),
                nullable=False,
            )
        )


def downgrade() -> None:
    """Remove per-product sale classification."""
    with op.batch_alter_table("tracked_product_sales") as batch_op:
        batch_op.drop_column("classification_evidence")
        batch_op.drop_column("classification_decision")
