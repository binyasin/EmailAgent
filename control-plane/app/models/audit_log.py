from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class AuditLog(TimestampMixin, Base):
    """Append-only. No update/delete route is exposed anywhere in the API."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    actor_type: Mapped[str] = mapped_column(String(20))  # "user" | "agent" | "system"
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str] = mapped_column(String(64))
    log_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
