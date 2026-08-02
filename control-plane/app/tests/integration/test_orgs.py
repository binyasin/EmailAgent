from app.core.security import create_access_token, verify_password
from app.models.org import Org
from app.models.user import User


def _seed_org(db_session, *, suffix: str):
    org = Org(id=f"org-{suffix}", name="Test Org")
    admin = User(
        id=f"admin-{suffix}",
        org_id=org.id,
        email=f"admin-{suffix}@example.com",
        hashed_password="unused",
        role="org_admin",
    )
    db_session.add_all([org, admin])
    db_session.commit()
    return org, admin


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def test_org_admin_can_invite_member_and_temp_password_works(client, db_session):
    org, admin = _seed_org(db_session, suffix="a")

    resp = client.post(
        "/api/v1/orgs/invite",
        json={"email": "newbie@example.com", "role": "member"},
        headers=_headers(admin),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "member"

    invited = db_session.query(User).filter(User.email == "newbie@example.com").one()
    assert verify_password(body["temporary_password"], invited.hashed_password)


def test_cannot_invite_with_duplicate_email(client, db_session):
    org, admin = _seed_org(db_session, suffix="b")
    client.post(
        "/api/v1/orgs/invite",
        json={"email": "dup@example.com", "role": "member"},
        headers=_headers(admin),
    )
    resp = client.post(
        "/api/v1/orgs/invite",
        json={"email": "dup@example.com", "role": "member"},
        headers=_headers(admin),
    )
    assert resp.status_code == 409


def test_member_cannot_invite(client, db_session):
    org, admin = _seed_org(db_session, suffix="c")
    member = User(
        id="member-c", org_id=org.id, email="m-c@example.com", hashed_password="x", role="member"
    )
    db_session.add(member)
    db_session.commit()

    resp = client.post(
        "/api/v1/orgs/invite",
        json={"email": "x@example.com", "role": "member"},
        headers=_headers(member),
    )
    assert resp.status_code == 403


def test_cannot_demote_the_last_org_admin(client, db_session):
    org, admin = _seed_org(db_session, suffix="d")

    resp = client.patch(
        f"/api/v1/orgs/members/{admin.id}/role",
        json={"role": "member"},
        headers=_headers(admin),
    )
    assert resp.status_code == 409


def test_can_demote_org_admin_when_another_admin_remains(client, db_session):
    org, admin = _seed_org(db_session, suffix="e")
    second_admin = User(
        id="admin2-e", org_id=org.id, email="admin2-e@example.com", hashed_password="x", role="org_admin"
    )
    db_session.add(second_admin)
    db_session.commit()

    resp = client.patch(
        f"/api/v1/orgs/members/{admin.id}/role",
        json={"role": "member"},
        headers=_headers(second_admin),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"


def test_cannot_remove_the_last_org_admin(client, db_session):
    org, admin = _seed_org(db_session, suffix="f")

    resp = client.delete(f"/api/v1/orgs/members/{admin.id}", headers=_headers(admin))
    assert resp.status_code == 409


def test_members_scoped_per_org(client, db_session):
    org_a, admin_a = _seed_org(db_session, suffix="g")
    org_b, admin_b = _seed_org(db_session, suffix="h")

    resp = client.get("/api/v1/orgs/members", headers=_headers(admin_a))
    assert resp.status_code == 200
    emails = {m["email"] for m in resp.json()}
    assert emails == {admin_a.email}
