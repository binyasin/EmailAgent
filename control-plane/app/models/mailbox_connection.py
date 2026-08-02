from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class MailboxConnection(TimestampMixin, Base):
    __tablename__ = "mailbox_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(20))  # "gmail" | "outlook"
    email_address: Mapped[str] = mapped_column(String(320))
    refresh_token_encrypted: Mapped[str] = mapped_column(String(2048))
    access_token_cache_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scopes: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(20), default="connected")
