from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class AgentCell(TimestampMixin, Base):
    """Phase 3+: one row per tenant's OpenClaw Fleet cell. Unused in Phase 1,
    where a single hand-configured OpenClaw container serves the dev org."""

    __tablename__ = "agent_cells"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orgs.id", ondelete="CASCADE"), unique=True, index=True
    )
    tenant_key: Mapped[str] = mapped_column(String(64), unique=True)  # Fleet cell id
    status: Mapped[str] = mapped_column(String(20), default="provisioning")
    # provisioning | running | stopped | error | deprovisioned
    image_ref: Mapped[str] = mapped_column(String(255), default="")
    host_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gateway_token_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    config_version: Mapped[int] = mapped_column(Integer, default=1)
