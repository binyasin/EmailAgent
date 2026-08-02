from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class VipRule(TimestampMixin, Base):
    __tablename__ = "vip_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    # An exact email address ("ceo@example.com") or a domain match
    # ("@example.com"), matched by the vip-escalation skill against the
    # rendered vip-list.md workspace file — see config_renderer.py.
    sender_pattern: Mapped[str] = mapped_column(String(320))
    priority: Mapped[int] = mapped_column(Integer, default=0)
