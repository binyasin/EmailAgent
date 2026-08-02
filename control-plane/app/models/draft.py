from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class Draft(TimestampMixin, Base):
    """Metadata only — full email body is fetched from the provider API on
    demand when a human opens the draft for review, not cached here, to
    minimize PII at rest in the control-plane database."""

    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    mailbox_connection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mailbox_connections.id", ondelete="CASCADE")
    )
    provider_draft_id: Mapped[str] = mapped_column(String(255))
    thread_id: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(998), default="")
    snippet: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    # pending_review | approved | rejected | sent | failed
    created_by_skill: Mapped[str] = mapped_column(String(100), default="draft-reply")
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
