from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_cell_service_token
from app.db.session import get_db
from app.services.fleet_cli import CellProvisioner, SubprocessFleetCliRunner

DbSession = Session


def get_session(db: Session = Depends(get_db)) -> Generator[Session, None, None]:
    try:
        yield db
    except HTTPException:
        # A route can deliberately record state (e.g. mark a draft "failed"
        # + write an audit log entry) before raising an HTTPException to
        # report the error to the client — that's still a real outcome we
        # want persisted, not a DB-layer failure, so commit rather than
        # discard it.
        db.commit()
        raise
    except Exception:
        db.rollback()
        raise
    else:
        db.commit()


def get_cell_org_id(x_cell_service_token: str = Header(default="")) -> str:
    """Authenticates AND identifies the calling agent cell via a per-org
    JWT minted at provisioning time (see core.security.create_cell_service_token
    / workers/provision_cell.py). The returned org_id is the source of
    truth for which tenant this call is scoped to — routes must use it
    instead of trusting any client-supplied tenant_id/org_id parameter."""
    if not x_cell_service_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing cell service token")
    return decode_cell_service_token(x_cell_service_token)


def get_cell_provisioner() -> CellProvisioner:
    """Overridden in tests with a fake FleetCliRunner — the real
    implementation shells out to the `openclaw` binary, which isn't
    installed in the Phase 1/2 dev Docker Compose stack (that uses a single
    static `openclaw` container, not Fleet), so routes that depend on this
    are Phase 3+ multi-tenant-only and will fail loudly if called without a
    real OpenClaw + Fleet install available."""
    return CellProvisioner(SubprocessFleetCliRunner())
