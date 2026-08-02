from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DraftIngestRequest(BaseModel):
    """Posted by the gmail-mcp/outlook-mcp adapter after create_draft succeeds."""

    mailbox_connection_id: str
    provider_draft_id: str
    thread_id: str
    subject: str = ""
    snippet: str = ""
    created_by_skill: str = "draft-reply"


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mailbox_connection_id: str
    provider_draft_id: str
    thread_id: str
    subject: str
    snippet: str
    status: str
    created_by_skill: str
    created_at: datetime


class DraftReviewRequest(BaseModel):
    edited_body: str | None = None
