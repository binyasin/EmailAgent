"""add digest_runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "digest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_digest_runs_org_id", "digest_runs", ["org_id"])


def downgrade() -> None:
    op.drop_table("digest_runs")
