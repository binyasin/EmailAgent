"""Orchestrates provisioning/updating a tenant's OpenClaw Fleet cell:
render config -> write it into Fleet's own per-tenant state directory ->
create-or-update the cell via Fleet -> record the result on the AgentCell row.

Wrapped in a process-wide lock because Fleet's cell state is file-based per
host (see docs/openclaw-integration-notes.md) — concurrent `fleet` mutations
against the same host must not race. A single `threading.Lock` is enough for
Phase 3's single-host dev/staging scope; a real multi-host deployment would
need a distributed lock (e.g. a DB advisory lock keyed by host), which is a
Phase 4 concern once there's more than one cell host to coordinate across.
"""

import threading
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_cell_service_token
from app.models.agent_cell import AgentCell
from app.models.org import Org
from app.services.audit import record_audit_event
from app.services.config_renderer import render_tenant_config_files
from app.services.fleet_cli import CellProvisioner
from app.services.token_crypto import encrypt_token

_provision_lock = threading.Lock()


def _cell_config_dir(tenant_key: str) -> Path:
    # Fleet-managed per-tenant directory, mounted into the container at
    # /home/node/.openclaw — confirmed against docs.openclaw.ai/cli/fleet.
    # See docs/openclaw-integration-notes.md.
    openclaw_state_dir = Path(get_settings().openclaw_state_dir).expanduser()
    return openclaw_state_dir / "fleet" / "cells" / tenant_key


def _stage_config_files(tenant_key: str, files: dict[str, str]) -> Path:
    state_dir = _cell_config_dir(tenant_key)
    state_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (state_dir / filename).write_text(content, encoding="utf-8")
    return state_dir


def provision_cell(
    db: Session,
    org_id: str,
    *,
    cell_provisioner: CellProvisioner,
    image_ref: str | None = None,
) -> AgentCell:
    """Idempotent: first call creates the cell, later calls re-render config
    and restart it. Safe to call every time a mailbox is connected or a
    skill setting changes."""

    org = db.get(Org, org_id)
    if org is None:
        raise ValueError(f"unknown org {org_id}")

    image_ref = image_ref or get_settings().default_cell_image
    agent_id = f"{org_id}-primary"

    with _provision_lock:
        cell = db.scalar(select(AgentCell).where(AgentCell.org_id == org_id))
        config_files = render_tenant_config_files(db, org_id, agent_id=agent_id)

        if cell is None:
            # Fleet seeds its own default config into
            # <state-dir>/fleet/cells/<tenant>/ on create, so the cell must
            # exist (created with no_start=True) before we overwrite that
            # directory with our rendered config and only then start it —
            # see docs/openclaw-integration-notes.md.
            tenant_key = org_id

            # Minted once, at creation — this is the credential the cell's
            # MCP servers use to call the token-broker/ingest endpoints, with
            # org_id baked into the token itself (see core/security.py's
            # CELL_SERVICE_AUDIENCE docstring for why this replaced an
            # earlier global-shared-secret design that let any cell
            # impersonate any tenant).
            cell_service_token = create_cell_service_token(org_id=org_id)
            create_result = cell_provisioner.create(
                tenant_key,
                image=image_ref,
                env={
                    "TENANT_ID": org_id,
                    "CELL_SERVICE_TOKEN": cell_service_token,
                    # Resolves models.providers.anthropic.apiKey's ${ANTHROPIC_API_KEY}
                    # in the rendered openclaw.json — see config_renderer.py.
                    "ANTHROPIC_API_KEY": get_settings().anthropic_api_key,
                    # Resolves models.providers.google.apiKey's ${GEMINI_API_KEY}.
                    "GEMINI_API_KEY": get_settings().gemini_api_key,
                    # Resolves models.providers.openrouter.apiKey's ${OPENROUTER_API_KEY}.
                    "OPENROUTER_API_KEY": get_settings().openrouter_api_key,
                    # Resolves models.providers.openai.apiKey's ${OPENAI_API_KEY}.
                    "OPENAI_API_KEY": get_settings().openai_api_key,
                },
                no_start=True,
            )
            _stage_config_files(create_result.tenant_key, config_files)
            cell = AgentCell(
                org_id=org_id,
                tenant_key=create_result.tenant_key,
                image_ref=image_ref,
                host_port=create_result.host_port,
                gateway_token_encrypted=(
                    encrypt_token(create_result.gateway_token)
                    if create_result.gateway_token
                    else None
                ),
                status="provisioning",
                config_version=1,
            )
            db.add(cell)
            db.flush()
            cell_provisioner.start(cell.tenant_key)
            action = "cell.created"
        else:
            # The cell's directory already exists from a prior create, so it's
            # safe to overwrite the config files before restarting.
            _stage_config_files(cell.tenant_key, config_files)
            cell.config_version += 1
            cell_provisioner.restart(cell.tenant_key)
            action = "cell.config_updated"

        cell.status = "running"

        record_audit_event(
            db,
            org_id=org_id,
            actor_type="system",
            actor_id="provisioner",
            action=action,
            resource_type="agent_cell",
            resource_id=cell.id,
            metadata={"tenant_key": cell.tenant_key, "config_version": cell.config_version},
        )
        return cell


def deprovision_cell(
    db: Session, org_id: str, *, cell_provisioner: CellProvisioner, purge_data: bool = False
) -> None:
    with _provision_lock:
        cell = db.scalar(select(AgentCell).where(AgentCell.org_id == org_id))
        if cell is None:
            return

        cell_provisioner.remove(cell.tenant_key, purge_data=purge_data)
        cell.status = "deprovisioned"

        record_audit_event(
            db,
            org_id=org_id,
            actor_type="system",
            actor_id="provisioner",
            action="cell.deprovisioned",
            resource_type="agent_cell",
            resource_id=cell.id,
            metadata={"tenant_key": cell.tenant_key, "purge_data": purge_data},
        )
