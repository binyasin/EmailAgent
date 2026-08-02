from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MailboxConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    email_address: str
    status: str
    created_at: datetime


class OAuthStartResponse(BaseModel):
    authorization_url: str
