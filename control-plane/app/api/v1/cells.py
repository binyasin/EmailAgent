from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_cell_provisioner, get_session
from app.core.security import CurrentUser, Role, require_org_scope, require_role
from app.models.agent_cell import AgentCell
from app.schemas.cell import AgentCellOut
from app.services.audit import record_audit_event
from app.services.fleet_cli import CellProvisioner, FleetCliError
from app.workers.provision_cell import provision_cell

router = APIRouter(prefix="/cells", tags=["cells"])


@router.get("", response_model=list[AgentCellOut])
def list_cells(
    db=Depends(get_session), user: CurrentUser = Depends(require_role(Role.PLATFORM_ADMIN))
):
    """Platform-admin only — cross-org cell fleet view (the dashboard's
    AdminCells screen)."""
    return db.scalars(select(AgentCell).order_by(AgentCell.created_at.desc())).all()


@router.get("/mine", response_model=AgentCellOut)
def get_my_cell(db=Depends(get_session), user: CurrentUser = Depends(require_org_scope)):
    cell = db.scalar(select(AgentCell).where(AgentCell.org_id == user.org_id))
    if cell is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cell provisioned for this org yet")
    return cell


@router.post("/mine/provision", response_model=AgentCellOut)
def provision_my_cell(
    db=Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.ORG_ADMIN)),
    provisioner: CellProvisioner = Depends(get_cell_provisioner),
):
    """Explicit, org-admin-triggered provisioning — deliberately not wired
    to fire automatically on mailbox connect, since that would break the
    Phase 1/2 static single-container dev stack for anyone without a real
    Fleet install. See app/workers/provision_cell.py."""
    if user.org_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no org")
    try:
        return provision_cell(db, user.org_id, cell_provisioner=provisioner)
    except FleetCliError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.post("/{org_id}/restart", response_model=AgentCellOut)
def restart_cell(
    org_id: str,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.PLATFORM_ADMIN)),
    provisioner: CellProvisioner = Depends(get_cell_provisioner),
):
    cell = db.scalar(select(AgentCell).where(AgentCell.org_id == org_id))
    if cell is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cell for this org")

    try:
        provisioner.restart(cell.tenant_key)
    except FleetCliError as exc:
        cell.status = "error"
        record_audit_event(
            db,
            org_id=org_id,
            actor_type="user",
            actor_id=user.user_id,
            action="cell.restart_failed",
            resource_type="agent_cell",
            resource_id=cell.id,
            metadata={"error": str(exc)},
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    cell.status = "running"
    record_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="cell.restarted",
        resource_type="agent_cell",
        resource_id=cell.id,
    )
    return cell
