"""Create tracked products and completed-sale storage.

Revision ID: 0001
Revises:
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial local persistence schema."""
    op.create_table(
        "tracked_products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("category_id", sa.String(length=32), nullable=True),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("minimum_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("maximum_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("price_basis", sa.String(length=32), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("listing_formats", sa.JSON(), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("marketplace_country", sa.String(length=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("standalone_working_only", sa.Boolean(), nullable=False),
        sa.Column("required_title_terms", sa.JSON(), nullable=False),
        sa.Column("additional_exclusion_terms", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tracked_products"),
    )
    op.create_table(
        "sale_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_item_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("sold_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("shipping_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("sold_at", sa.DateTime(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("raw_record_hash", sa.String(length=128), nullable=False),
        sa.Column("condition", sa.String(length=32), nullable=True),
        sa.Column("listing_format", sa.String(length=32), nullable=True),
        sa.Column("best_offer", sa.Boolean(), nullable=True),
        sa.Column("bid_count", sa.Integer(), nullable=True),
        sa.Column("listing_url", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("seller_name", sa.String(length=200), nullable=True),
        sa.Column(
            "seller_feedback_percentage",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column("seller_feedback_count", sa.Integer(), nullable=True),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("part_number", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sale_observations"),
        sa.UniqueConstraint(
            "source",
            "external_item_id",
            name="uq_sale_observations_source_item",
        ),
    )
    op.create_index(
        "ix_sale_observations_product",
        "sale_observations",
        ["brand", "model"],
    )
    op.create_index(
        "ix_sale_observations_sold_at",
        "sale_observations",
        ["sold_at"],
    )
    op.create_table(
        "source_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sale_observation_id", sa.Integer(), nullable=False),
        sa.Column("raw_record_hash", sa.String(length=128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sale_observation_id"],
            ["sale_observations.id"],
            name="fk_source_revisions_sale_observation_id_sale_observations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_revisions"),
        sa.UniqueConstraint(
            "sale_observation_id",
            "raw_record_hash",
            name="uq_source_revisions_observation_hash",
        ),
    )
    op.create_table(
        "tracked_product_sales",
        sa.Column("tracked_product_id", sa.String(length=36), nullable=False),
        sa.Column("sale_observation_id", sa.Integer(), nullable=False),
        sa.Column("matched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sale_observation_id"],
            ["sale_observations.id"],
            name="fk_tracked_product_sales_sale_observation_id_sale_observations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tracked_product_id"],
            ["tracked_products.id"],
            name="fk_tracked_product_sales_tracked_product_id_tracked_products",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "tracked_product_id",
            "sale_observation_id",
            name="pk_tracked_product_sales",
        ),
    )


def downgrade() -> None:
    """Remove the initial local persistence schema."""
    op.drop_table("tracked_product_sales")
    op.drop_table("source_revisions")
    op.drop_index("ix_sale_observations_sold_at", table_name="sale_observations")
    op.drop_index("ix_sale_observations_product", table_name="sale_observations")
    op.drop_table("sale_observations")
    op.drop_table("tracked_products")
