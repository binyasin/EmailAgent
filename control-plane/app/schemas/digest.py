from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DigestIngestRequest(BaseModel):
    """Posted by the digest skill's `notify_digest_ready` tool call."""

    period: str  # "daily" | "weekly"
    summary_text: str


class DigestRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    period: str
    summary_text: str
    created_at: datetime
