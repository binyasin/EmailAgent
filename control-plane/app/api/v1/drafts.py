from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_session
from app.core.security import CurrentUser, require_org_scope
from app.models.draft import Draft
from app.models.mailbox_connection import MailboxConnection
from app.schemas.draft import DraftOut, DraftReviewRequest
from app.services.audit import record_audit_event
from app.services.email_provider.gmail import GmailProvider
from app.services.email_provider.outlook import OutlookProvider

router = APIRouter(prefix="/drafts", tags=["drafts"])

_PROVIDERS = {"gmail": GmailProvider(), "outlook": OutlookProvider()}


def _get_org_draft(db, org_id: str, draft_id: str) -> Draft:
    draft = db.scalar(select(Draft).where(Draft.id == draft_id, Draft.org_id == org_id))
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    return draft


@router.get("", response_model=list[DraftOut])
def list_drafts(
    status_filter: str | None = None,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_scope),
):
    query = select(Draft).where(Draft.org_id == user.org_id)
    if status_filter:
        query = query.where(Draft.status == status_filter)
    return db.scalars(query.order_by(Draft.created_at.desc())).all()


@router.post("/{draft_id}/approve", response_model=DraftOut)
def approve_draft(
    draft_id: str,
    payload: DraftReviewRequest,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_scope),
):
    draft = _get_org_draft(db, user.org_id, draft_id)
    if draft.status != "pending_review":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Draft is '{draft.status}', not reviewable")

    connection = db.get(MailboxConnection, draft.mailbox_connection_id)
    if connection is None or connection.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mailbox connection not found")

    provider = _PROVIDERS.get(connection.provider)
    if provider is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported provider {connection.provider}")

    try:
        provider.send_draft(connection, draft.provider_draft_id)
    except Exception as exc:  # provider API failure — keep draft reviewable, don't lose state
        draft.status = "failed"
        record_audit_event(
            db,
            org_id=user.org_id,
            actor_type="user",
            actor_id=user.user_id,
            action="draft.send_failed",
            resource_type="draft",
            resource_id=draft.id,
            metadata={"error": str(exc)},
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to send draft via provider") from exc

    draft.status = "sent"
    draft.reviewed_by_user_id = user.user_id
    draft.reviewed_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="draft.approved",
        resource_type="draft",
        resource_id=draft.id,
    )
    return draft


@router.post("/{draft_id}/reject", response_model=DraftOut)
def reject_draft(
    draft_id: str,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_scope),
):
    draft = _get_org_draft(db, user.org_id, draft_id)
    if draft.status != "pending_review":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Draft is '{draft.status}', not reviewable")

    draft.status = "rejected"
    draft.reviewed_by_user_id = user.user_id
    draft.reviewed_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="draft.rejected",
        resource_type="draft",
        resource_id=draft.id,
    )
    return draft
