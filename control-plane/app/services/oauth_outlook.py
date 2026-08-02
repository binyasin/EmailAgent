from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.mailbox_connection import MailboxConnection
from app.services.email_provider.outlook import OUTLOOK_SCOPES, build_msal_app
from app.services.token_crypto import encrypt_token


def get_authorization_url(state: str) -> str:
    settings = get_settings()
    app = build_msal_app()
    return app.get_authorization_request_url(
        OUTLOOK_SCOPES,
        state=state,
        redirect_uri=settings.ms_oauth_redirect_uri,
    )


def complete_oauth_and_store_connection(
    db: Session, *, org_id: str, owner_user_id: str, authorization_code: str
) -> MailboxConnection:
    settings = get_settings()
    app = build_msal_app()
    result = app.acquire_token_by_authorization_code(
        authorization_code,
        scopes=OUTLOOK_SCOPES,
        redirect_uri=settings.ms_oauth_redirect_uri,
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"Outlook OAuth exchange failed: {result.get('error_description', result)}"
        )
    if "refresh_token" not in result:
        raise RuntimeError(
            "Outlook OAuth exchange did not return a refresh_token — ensure 'offline_access' "
            "is included in the requested scopes and the app registration allows it."
        )

    profile = httpx.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {result['access_token']}"},
        timeout=30,
    ).json()
    email_address = profile.get("mail") or profile.get("userPrincipalName")

    connection = MailboxConnection(
        org_id=org_id,
        owner_user_id=owner_user_id,
        provider="outlook",
        email_address=email_address,
        refresh_token_encrypted=encrypt_token(result["refresh_token"]),
        access_token_cache_encrypted=encrypt_token(result["access_token"]),
        token_expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=result.get("expires_in", 3600)),
        scopes=" ".join(OUTLOOK_SCOPES),
        status="connected",
    )
    db.add(connection)
    db.flush()
    return connection
