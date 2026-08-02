from app.core.security import create_access_token
from app.models.org import Org
from app.models.user import User
from app.models.vip_rule import VipRule


def _seed_org(db_session, *, suffix: str):
    org = Org(id=f"org-{suffix}", name="Test Org")
    admin = User(
        id=f"admin-{suffix}",
        org_id=org.id,
        email=f"admin-{suffix}@example.com",
        hashed_password="unused",
        role="org_admin",
    )
    member = User(
        id=f"member-{suffix}",
        org_id=org.id,
        email=f"member-{suffix}@example.com",
        hashed_password="unused",
        role="member",
    )
    db_session.add_all([org, admin, member])
    db_session.commit()
    return org, admin, member


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def test_org_admin_can_toggle_a_known_skill(client, db_session):
    org, admin, _member = _seed_org(db_session, suffix="a")

    resp = client.put(
        "/api/v1/skill-settings/vip-escalation",
        json={"enabled": True, "params": {}},
        headers=_headers(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["skill_name"] == "vip-escalation"
    assert resp.json()["enabled"] is True

    listed = client.get("/api/v1/skill-settings", headers=_headers(admin))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_member_cannot_toggle_a_skill(client, db_session):
    org, _admin, member = _seed_org(db_session, suffix="b")

    resp = client.put(
        "/api/v1/skill-settings/vip-escalation",
        json={"enabled": True, "params": {}},
        headers=_headers(member),
    )
    assert resp.status_code == 403


def test_unknown_skill_name_is_rejected(client, db_session):
    org, admin, _member = _seed_org(db_session, suffix="c")

    resp = client.put(
        "/api/v1/skill-settings/not-a-real-skill",
        json={"enabled": True, "params": {}},
        headers=_headers(admin),
    )
    assert resp.status_code == 400


def test_org_admin_can_manage_vip_rules_and_member_can_only_read(client, db_session):
    org, admin, member = _seed_org(db_session, suffix="d")

    created = client.post(
        "/api/v1/vip-rules",
        json={"sender_pattern": "ceo@example.com", "priority": 10},
        headers=_headers(admin),
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]

    member_read = client.get("/api/v1/vip-rules", headers=_headers(member))
    assert member_read.status_code == 200
    assert len(member_read.json()) == 1

    member_write = client.post(
        "/api/v1/vip-rules",
        json={"sender_pattern": "other@example.com"},
        headers=_headers(member),
    )
    assert member_write.status_code == 403

    deleted = client.delete(f"/api/v1/vip-rules/{rule_id}", headers=_headers(admin))
    assert deleted.status_code == 204
    assert db_session.get(VipRule, rule_id) is None


def test_vip_rules_are_scoped_per_org(client, db_session):
    org_a, admin_a, _m = _seed_org(db_session, suffix="e")
    org_b, admin_b, _m2 = _seed_org(db_session, suffix="f")

    client.post(
        "/api/v1/vip-rules",
        json={"sender_pattern": "a@example.com"},
        headers=_headers(admin_a),
    )

    resp_b = client.get("/api/v1/vip-rules", headers=_headers(admin_b))
    assert resp_b.status_code == 200
    assert resp_b.json() == []
