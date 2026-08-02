"""add stripe customer/subscription id to orgs

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.add_column("orgs", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))
    op.create_index(
        "ix_orgs_stripe_customer_id", "orgs", ["stripe_customer_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_orgs_stripe_customer_id", table_name="orgs")
    op.drop_column("orgs", "stripe_subscription_id")
    op.drop_column("orgs", "stripe_customer_id")
