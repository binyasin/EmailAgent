from datetime import datetime, timedelta, timezone

import httpx
import msal

from app.core.config import get_settings
from app.models.mailbox_connection import MailboxConnection
from app.services.email_provider.base import EmailProvider
from app.services.token_crypto import decrypt_token, encrypt_token

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

OUTLOOK_SCOPES = [
    "offline_access",
    "User.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.ReadWrite",
]


def build_msal_app() -> msal.ConfidentialClientApplication:
    settings = get_settings()
    return msal.ConfidentialClientApplication(
        client_id=settings.ms_oauth_client_id,
        client_credential=settings.ms_oauth_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.ms_oauth_tenant_id}",
    )


class OutlookProvider(EmailProvider):
    def refresh_access_token(self, connection: MailboxConnection) -> str:
        if (
            connection.access_token_cache_encrypted
            and connection.token_expires_at
            and connection.token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=30)
        ):
            return decrypt_token(connection.access_token_cache_encrypted)

        app = build_msal_app()
        result = app.acquire_token_by_refresh_token(
            decrypt_token(connection.refresh_token_encrypted), scopes=OUTLOOK_SCOPES
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Failed to refresh Outlook access token: {result.get('error_description', result)}"
            )

        connection.access_token_cache_encrypted = encrypt_token(result["access_token"])
        connection.token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=result.get("expires_in", 3600)
        )
        # Microsoft may rotate the refresh token on use — persist the new one if issued.
        if "refresh_token" in result:
            connection.refresh_token_encrypted = encrypt_token(result["refresh_token"])
        return result["access_token"]

    def send_draft(self, connection: MailboxConnection, provider_draft_id: str) -> str:
        access_token = self.refresh_access_token(connection)
        res = httpx.post(
            f"{GRAPH_API_BASE}/me/messages/{provider_draft_id}/send",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if res.status_code >= 400:
            raise RuntimeError(f"Graph send failed: {res.status_code} {res.text}")
        return provider_draft_id
