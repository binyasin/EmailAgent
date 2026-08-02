"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orgs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan_tier", sa.String(50), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "mailbox_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(2048), nullable=False),
        sa.Column("access_token_cache_encrypted", sa.String(2048), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String(1024), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mailbox_connections_org_id", "mailbox_connections", ["org_id"])

    op.create_table(
        "drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "mailbox_connection_id",
            sa.String(36),
            sa.ForeignKey("mailbox_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_draft_id", sa.String(255), nullable=False),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(998), nullable=False, server_default=""),
        sa.Column("snippet", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_review"),
        sa.Column("created_by_skill", sa.String(100), nullable=False, server_default="draft-reply"),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_drafts_org_id", "drafts", ["org_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("log_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])

    op.create_table(
        "agent_cells",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="provisioning"),
        sa.Column("image_ref", sa.String(255), nullable=False, server_default=""),
        sa.Column("host_port", sa.Integer(), nullable=True),
        sa.Column("gateway_token_encrypted", sa.String(2048), nullable=True),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_cells_org_id", "agent_cells", ["org_id"], unique=True)
    op.create_index("ix_agent_cells_tenant_key", "agent_cells", ["tenant_key"], unique=True)

    op.create_table(
        "org_skill_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "skill_name", name="uq_org_skill"),
    )
    op.create_index("ix_org_skill_settings_org_id", "org_skill_settings", ["org_id"])


def downgrade() -> None:
    op.drop_table("org_skill_settings")
    op.drop_table("agent_cells")
    op.drop_table("audit_logs")
    op.drop_table("drafts")
    op.drop_table("mailbox_connections")
    op.drop_table("users")
    op.drop_table("orgs")
