from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class DigestRun(TimestampMixin, Base):
    __tablename__ = "digest_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[str] = mapped_column(String(10))  # "daily" | "weekly"
    summary_text: Mapped[str] = mapped_column(Text)
