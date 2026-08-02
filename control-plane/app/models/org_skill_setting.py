from sqlalchemy import JSON, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class OrgSkillSetting(TimestampMixin, Base):
    __tablename__ = "org_skill_settings"
    __table_args__ = (UniqueConstraint("org_id", "skill_name", name="uq_org_skill"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    skill_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
