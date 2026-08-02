from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_cell_org_id, get_session
from app.models.digest_run import DigestRun
from app.models.org import Org
from app.schemas.digest import DigestIngestRequest, DigestRunOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/internal/v1/digests", tags=["internal"])


@router.post("/ingest", response_model=DigestRunOut, status_code=status.HTTP_201_CREATED)
def ingest_digest(
    payload: DigestIngestRequest,
    db=Depends(get_session),
    org_id: str = Depends(get_cell_org_id),
):
    """Called by the `digest` skill's `notify_digest_ready` tool once a
    periodic summary has been assembled — stores it for the dashboard's
    Digest view rather than emailing it directly. org_id comes from the
    caller's verified cell-service token, not a client-supplied parameter."""

    org = db.get(Org, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown org")

    digest = DigestRun(org_id=org_id, period=payload.period, summary_text=payload.summary_text)
    db.add(digest)
    db.flush()

    record_audit_event(
        db,
        org_id=org_id,
        actor_type="agent",
        actor_id="digest",
        action="digest.created",
        resource_type="digest_run",
        resource_id=digest.id,
        metadata={"period": payload.period},
    )
    return digest
