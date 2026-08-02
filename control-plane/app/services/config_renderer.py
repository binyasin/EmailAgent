"""Renders the files that get mounted into a tenant's OpenClaw cell —
openclaw.json (from the openclaw.json5.jinja template) and vip-list.md —
from this org's DB state (OrgSkillSetting, MailboxConnection, VipRule).

The rendering functions here are pure (template in, string out) and unit
tested without a database. `render_tenant_config_files` is the DB-aware
orchestrator that `cell_provisioner.py` (Phase 3 provisioning flow) calls.

style-profile.md is deliberately NOT rendered here — it accumulates learned
content inside the cell's own persistent volume over time, and re-rendering
it from DB state on every config update would clobber that. It's seeded
once from agent-runtime/templates/style-profile.md at first provision only.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mailbox_connection import MailboxConnection
from app.models.org_skill_setting import OrgSkillSetting
from app.models.vip_rule import VipRule

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "agent-runtime" / "templates"

# Every tool exposed by both gmail-mcp and outlook-mcp — kept as one list
# since the two servers were deliberately built with matching tool names so
# a skill's instructions don't need to branch on provider. Must be updated
# if either MCP server's tool surface changes.
TOOL_NAMES = [
    "search_threads",
    "get_message",
    "get_thread",
    "list_drafts",
    "create_draft",
    "update_draft",
    "list_labels",
    "create_label",
    "label_message",
    "label_thread",
    "apply_sensitive_thread_label",
    "find_availability",
    "list_events",
    "create_event",
    "notify_digest_ready",
]

# Baseline skills for an org with no explicit OrgSkillSetting rows yet —
# the safe, human-approval-gated core (triage + draft-reply), matching the
# Phase 1 default. Everything else is opt-in via the dashboard.
DEFAULT_ENABLED_SKILLS = ["triage", "draft-reply"]

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_openclaw_config(
    *, org_id: str, agent_id: str, providers: list[str], enabled_skills: list[str]
) -> str:
    if not providers:
        raise ValueError(f"org {org_id} has no connected mailbox providers to render config for")

    template = _env.get_template("openclaw.json5.jinja")
    return template.render(
        org_id=org_id,
        agent_id=agent_id,
        providers=providers,
        enabled_skills=["_shared", *enabled_skills],
        tool_names=TOOL_NAMES,
    )


def render_vip_list(rules: list[str]) -> str:
    template = _env.get_template("vip-list.md.jinja")
    return template.render(rules=rules)


def get_enabled_skill_ids(db: Session, org_id: str) -> list[str]:
    settings = db.scalars(
        select(OrgSkillSetting).where(
            OrgSkillSetting.org_id == org_id, OrgSkillSetting.enabled.is_(True)
        )
    ).all()
    if not settings:
        return list(DEFAULT_ENABLED_SKILLS)
    return [s.skill_name for s in settings]


def get_connected_providers(db: Session, org_id: str) -> list[str]:
    rows = db.scalars(
        select(MailboxConnection.provider).where(
            MailboxConnection.org_id == org_id, MailboxConnection.status == "connected"
        )
    ).all()
    return sorted(set(rows))


def get_vip_patterns(db: Session, org_id: str) -> list[str]:
    rules = db.scalars(
        select(VipRule).where(VipRule.org_id == org_id).order_by(VipRule.priority.desc())
    ).all()
    return [r.sender_pattern for r in rules]


def render_tenant_config_files(db: Session, org_id: str, *, agent_id: str) -> dict[str, str]:
    return {
        "openclaw.json": render_openclaw_config(
            org_id=org_id,
            agent_id=agent_id,
            providers=get_connected_providers(db, org_id),
            enabled_skills=get_enabled_skill_ids(db, org_id),
        ),
        "vip-list.md": render_vip_list(get_vip_patterns(db, org_id)),
    }
