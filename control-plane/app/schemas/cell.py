from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentCellOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    tenant_key: str
    status: str
    image_ref: str
    host_port: int | None
    config_version: int
    created_at: datetime
