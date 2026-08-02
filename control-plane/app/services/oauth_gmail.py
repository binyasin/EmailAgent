from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.models.mailbox_connection import MailboxConnection
from app.services.email_provider.gmail import build_oauth_flow
from app.services.token_crypto import encrypt_token


def get_authorization_url(state: str) -> str:
    flow = build_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url


def complete_oauth_and_store_connection(
    db: Session, *, org_id: str, owner_user_id: str, authorization_response_url: str
) -> MailboxConnection:
    flow = build_oauth_flow()
    flow.fetch_token(authorization_response=authorization_response_url)
    creds: Credentials = flow.credentials

    profile = (
        build("gmail", "v1", credentials=creds, cache_discovery=False)
        .users()
        .getProfile(userId="me")
        .execute()
    )
    email_address = profile["emailAddress"]

    connection = MailboxConnection(
        org_id=org_id,
        owner_user_id=owner_user_id,
        provider="gmail",
        email_address=email_address,
        refresh_token_encrypted=encrypt_token(creds.refresh_token),
        access_token_cache_encrypted=encrypt_token(creds.token) if creds.token else None,
        token_expires_at=creds.expiry,
        scopes=" ".join(creds.scopes or []),
        status="connected",
    )
    db.add(connection)
    db.flush()
    return connection
