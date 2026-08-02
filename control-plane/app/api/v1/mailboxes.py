import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.api.deps import get_session
from app.core.security import CurrentUser, require_org_scope
from app.models.mailbox_connection import MailboxConnection
from app.models.org import Org
from app.schemas.mailbox import MailboxConnectionOut, OAuthStartResponse
from app.services import oauth_gmail, oauth_outlook
from app.services.audit import record_audit_event
from app.services.billing import enforce_plan_limit

router = APIRouter(prefix="/mailboxes", tags=["mailboxes"])

# Phase 1/2: in-memory OAuth state -> (org_id, user_id) map. Fine for a
# single dev-mode process; Phase 3 should persist this (e.g. signed state
# param) once multiple control-plane instances are involved.
_oauth_state: dict[str, tuple[str, str]] = {}


def _check_mailbox_plan_limit(db, org_id: str) -> bool:
    """Returns True if under the plan's mailbox limit. Deliberately returns
    a bool rather than raising: these callback routes redirect the browser
    back to the dashboard on every other error path, so a raised
    HTTPException here would show a raw JSON error page instead."""
    org = db.get(Org, org_id)
    current_mailboxes = db.scalar(
        select(func.count()).select_from(MailboxConnection).where(
            MailboxConnection.org_id == org_id, MailboxConnection.status == "connected"
        )
    )
    try:
        enforce_plan_limit(plan_tier=org.plan_tier, resource="mailboxes", current_count=current_mailboxes)
        return True
    except HTTPException:
        return False


@router.get("", response_model=list[MailboxConnectionOut])
def list_mailboxes(db=Depends(get_session), user: CurrentUser = Depends(require_org_scope)):
    return db.scalars(
        select(MailboxConnection).where(MailboxConnection.org_id == user.org_id)
    ).all()


@router.get("/gmail/oauth/start", response_model=OAuthStartResponse)
def start_gmail_oauth(user: CurrentUser = Depends(require_org_scope)) -> OAuthStartResponse:
    state = uuid.uuid4().hex
    _oauth_state[state] = (user.org_id, user.user_id)
    return OAuthStartResponse(authorization_url=oauth_gmail.get_authorization_url(state))


@router.get("/gmail/oauth/callback")
def gmail_oauth_callback(request: Request, state: str, db=Depends(get_session)):
    org_id, user_id = _oauth_state.pop(state, (None, None))
    if org_id is None:
        return RedirectResponse(url="http://localhost:5173/mailboxes?error=invalid_state")
    if not _check_mailbox_plan_limit(db, org_id):
        return RedirectResponse(url="http://localhost:5173/mailboxes?error=plan_limit_exceeded")

    connection = oauth_gmail.complete_oauth_and_store_connection(
        db,
        org_id=org_id,
        owner_user_id=user_id,
        authorization_response_url=str(request.url),
    )
    record_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        action="mailbox.connected",
        resource_type="mailbox_connection",
        resource_id=connection.id,
        metadata={"provider": "gmail", "email_address": connection.email_address},
    )
    return RedirectResponse(url="http://localhost:5173/mailboxes?connected=1")


@router.get("/outlook/oauth/start", response_model=OAuthStartResponse)
def start_outlook_oauth(user: CurrentUser = Depends(require_org_scope)) -> OAuthStartResponse:
    state = uuid.uuid4().hex
    _oauth_state[state] = (user.org_id, user.user_id)
    return OAuthStartResponse(authorization_url=oauth_outlook.get_authorization_url(state))


@router.get("/outlook/oauth/callback")
def outlook_oauth_callback(code: str, state: str, db=Depends(get_session)):
    org_id, user_id = _oauth_state.pop(state, (None, None))
    if org_id is None:
        return RedirectResponse(url="http://localhost:5173/mailboxes?error=invalid_state")
    if not _check_mailbox_plan_limit(db, org_id):
        return RedirectResponse(url="http://localhost:5173/mailboxes?error=plan_limit_exceeded")

    connection = oauth_outlook.complete_oauth_and_store_connection(
        db,
        org_id=org_id,
        owner_user_id=user_id,
        authorization_code=code,
    )
    record_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        action="mailbox.connected",
        resource_type="mailbox_connection",
        resource_id=connection.id,
        metadata={"provider": "outlook", "email_address": connection.email_address},
    )
    return RedirectResponse(url="http://localhost:5173/mailboxes?connected=1")
