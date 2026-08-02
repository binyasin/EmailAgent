import json5

from app.models.mailbox_connection import MailboxConnection
from app.models.org import Org
from app.models.org_skill_setting import OrgSkillSetting
from app.models.vip_rule import VipRule
from app.services.config_renderer import (
    DEFAULT_ENABLED_SKILLS,
    get_connected_providers,
    get_enabled_skill_ids,
    get_vip_patterns,
    render_openclaw_config,
    render_tenant_config_files,
    render_vip_list,
)
from app.services.token_crypto import encrypt_token


def test_render_openclaw_config_includes_only_connected_providers():
    rendered = render_openclaw_config(
        org_id="org-1",
        agent_id="org-1-primary",
        providers=["gmail"],
        enabled_skills=["triage", "draft-reply"],
    )

    assert "gmail:" in rendered
    assert "outlook:" not in rendered

    parsed = json5.loads(rendered)
    assert set(parsed["mcp"]["servers"].keys()) == {"gmail"}
    assert parsed["agents"]["entries"]["org-1-primary"]["skills"] == [
        "_shared",
        "triage",
        "draft-reply",
    ]


def test_render_openclaw_config_includes_both_providers_when_both_connected():
    rendered = render_openclaw_config(
        org_id="org-2",
        agent_id="org-2-primary",
        providers=["gmail", "outlook"],
        enabled_skills=["triage"],
    )

    parsed = json5.loads(rendered)
    assert set(parsed["mcp"]["servers"].keys()) == {"gmail", "outlook"}


def test_render_openclaw_config_rejects_no_providers():
    import pytest

    with pytest.raises(ValueError, match="no connected mailbox providers"):
        render_openclaw_config(org_id="org-3", agent_id="a", providers=[], enabled_skills=[])


def test_render_vip_list_with_entries():
    rendered = render_vip_list(["ceo@example.com", "@board.example.com"])
    assert "ceo@example.com" in rendered
    assert "@board.example.com" in rendered


def test_render_vip_list_empty():
    rendered = render_vip_list([])
    assert "no VIP rules configured" in rendered


def _seed_mailbox(db_session, org_id: str, provider: str, status: str = "connected"):
    db_session.add(
        MailboxConnection(
            org_id=org_id,
            owner_user_id="user-x",
            provider=provider,
            email_address=f"{provider}@example.com",
            refresh_token_encrypted=encrypt_token("refresh"),
            status=status,
        )
    )


def test_get_enabled_skill_ids_defaults_when_none_configured(db_session):
    db_session.add(Org(id="org-default", name="Default Org"))
    db_session.commit()

    assert get_enabled_skill_ids(db_session, "org-default") == DEFAULT_ENABLED_SKILLS


def test_get_enabled_skill_ids_reflects_settings(db_session):
    db_session.add(Org(id="org-settings", name="Settings Org"))
    db_session.add(OrgSkillSetting(org_id="org-settings", skill_name="triage", enabled=True))
    db_session.add(OrgSkillSetting(org_id="org-settings", skill_name="digest", enabled=False))
    db_session.commit()

    assert get_enabled_skill_ids(db_session, "org-settings") == ["triage"]


def test_get_connected_providers_excludes_non_connected(db_session):
    db_session.add(Org(id="org-providers", name="Providers Org"))
    db_session.commit()
    _seed_mailbox(db_session, "org-providers", "gmail", status="connected")
    _seed_mailbox(db_session, "org-providers", "outlook", status="revoked")
    db_session.commit()

    assert get_connected_providers(db_session, "org-providers") == ["gmail"]


def test_render_tenant_config_files_end_to_end(db_session):
    db_session.add(Org(id="org-e2e", name="E2E Org"))
    db_session.commit()
    _seed_mailbox(db_session, "org-e2e", "gmail")
    db_session.add(VipRule(org_id="org-e2e", sender_pattern="ceo@example.com"))
    db_session.commit()

    files = render_tenant_config_files(db_session, "org-e2e", agent_id="org-e2e-primary")

    assert set(files.keys()) == {"openclaw.json", "vip-list.md"}
    parsed = json5.loads(files["openclaw.json"])
    assert set(parsed["mcp"]["servers"].keys()) == {"gmail"}
    assert "ceo@example.com" in files["vip-list.md"]
