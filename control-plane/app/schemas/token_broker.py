from pydantic import BaseModel


class AccessTokenOut(BaseModel):
    mailbox_connection_id: str
    provider: str
    email_address: str
    access_token: str
