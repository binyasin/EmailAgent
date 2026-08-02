from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_cell_org_id, get_session
from app.models.draft import Draft
from app.models.mailbox_connection import MailboxConnection
from app.schemas.draft import DraftIngestRequest, DraftOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/internal/v1/drafts", tags=["internal"])


@router.post("/ingest", response_model=DraftOut, status_code=status.HTTP_201_CREATED)
def ingest_draft(
    payload: DraftIngestRequest,
    db=Depends(get_session),
    org_id: str = Depends(get_cell_org_id),
):
    """Called by the gmail-mcp/outlook-mcp adapter right after `create_draft`
    succeeds against the provider API — this is our own endpoint, so the
    draft-approval flow doesn't depend on any undocumented OpenClaw event
    or telemetry API."""

    connection = db.get(MailboxConnection, payload.mailbox_connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown mailbox_connection_id")
    if connection.org_id != org_id:
        # A cell's token only authorizes it to act for its own org — without
        # this check, any cell could inject fake drafts into any other
        # tenant's approval inbox by guessing a mailbox_connection_id.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mailbox connection belongs to another org")

    existing = db.scalar(
        select(Draft).where(
            Draft.mailbox_connection_id == payload.mailbox_connection_id,
            Draft.provider_draft_id == payload.provider_draft_id,
        )
    )
    if existing is not None:
        return existing

    draft = Draft(
        org_id=connection.org_id,
        mailbox_connection_id=payload.mailbox_connection_id,
        provider_draft_id=payload.provider_draft_id,
        thread_id=payload.thread_id,
        subject=payload.subject,
        snippet=payload.snippet,
        created_by_skill=payload.created_by_skill,
        status="pending_review",
    )
    db.add(draft)
    db.flush()

    record_audit_event(
        db,
        org_id=connection.org_id,
        actor_type="agent",
        actor_id=payload.created_by_skill,
        action="draft.created",
        resource_type="draft",
        resource_id=draft.id,
        metadata={"thread_id": payload.thread_id},
    )
    return draft
