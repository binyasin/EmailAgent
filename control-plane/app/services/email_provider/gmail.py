from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.config import get_settings
from app.models.mailbox_connection import MailboxConnection
from app.services.email_provider.base import EmailProvider
from app.services.token_crypto import decrypt_token, encrypt_token

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def build_oauth_flow() -> Flow:
    settings = get_settings()
    client_config = {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=GMAIL_SCOPES)
    flow.redirect_uri = settings.google_oauth_redirect_uri
    return flow


class GmailProvider(EmailProvider):
    def refresh_access_token(self, connection: MailboxConnection) -> str:
        if (
            connection.access_token_cache_encrypted
            and connection.token_expires_at
            and connection.token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=30)
        ):
            return decrypt_token(connection.access_token_cache_encrypted)

        settings = get_settings()
        creds = Credentials(
            token=None,
            refresh_token=decrypt_token(connection.refresh_token_encrypted),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
        )
        creds.refresh(GoogleAuthRequest())
        connection.access_token_cache_encrypted = encrypt_token(creds.token)
        connection.token_expires_at = creds.expiry.replace(tzinfo=timezone.utc)
        return creds.token

    def send_draft(self, connection: MailboxConnection, provider_draft_id: str) -> str:
        access_token = self.refresh_access_token(connection)
        service = build(
            "gmail", "v1", credentials=Credentials(token=access_token), cache_discovery=False
        )
        result = (
            service.users()
            .drafts()
            .send(userId="me", body={"id": provider_draft_id})
            .execute()
        )
        return result["id"]
