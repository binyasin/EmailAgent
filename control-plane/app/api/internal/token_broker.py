from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_cell_org_id, get_session
from app.models.mailbox_connection import MailboxConnection
from app.schemas.token_broker import AccessTokenOut
from app.services.email_provider.gmail import GmailProvider
from app.services.email_provider.outlook import OutlookProvider

router = APIRouter(prefix="/internal/v1/tokens", tags=["internal"])

_PROVIDERS = {"gmail": GmailProvider(), "outlook": OutlookProvider()}


@router.get("/current", response_model=AccessTokenOut)
def get_current_access_token(
    provider: str = "gmail",
    db=Depends(get_session),
    org_id: str = Depends(get_cell_org_id),
):
    """Called by an agent cell's MCP server before each provider API call.

    Cells never persist a refresh token themselves — this endpoint is the
    only place a long-lived credential is ever touched, and it only ever
    hands back a short-lived access token. `org_id` comes from the caller's
    verified cell-service token (get_cell_org_id), never from a
    client-supplied parameter — a cell can only ever fetch its own org's
    tokens.
    """
    connection = db.scalar(
        select(MailboxConnection).where(
            MailboxConnection.org_id == org_id,
            MailboxConnection.provider == provider,
            MailboxConnection.status == "connected",
        )
    )
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No connected mailbox for tenant/provider")

    provider_impl = _PROVIDERS.get(provider)
    if provider_impl is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported provider {provider}")

    access_token = provider_impl.refresh_access_token(connection)
    return AccessTokenOut(
        mailbox_connection_id=connection.id,
        provider=provider,
        email_address=connection.email_address,
        access_token=access_token,
    )
