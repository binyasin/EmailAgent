import pytest

from app.api.deps import get_cell_provisioner
from app.core.security import create_access_token
from app.main import app
from app.models.agent_cell import AgentCell
from app.models.mailbox_connection import MailboxConnection
from app.models.org import Org
from app.models.user import User
from app.services.fleet_cli import CellProvisioner, FleetCliResult
from app.services.token_crypto import encrypt_token
from app.tests.unit.test_fleet_cli import FakeFleetCliRunner


@pytest.fixture()
def fake_provisioner():
    runner = FakeFleetCliRunner()
    runner.queue(
        "create",
        FleetCliResult(
            returncode=0, stdout="", stderr="", json={"host_port": 41001, "gateway_token": "tok"}
        ),
    )
    provisioner = CellProvisioner(runner)

    app.dependency_overrides[get_cell_provisioner] = lambda: provisioner
    try:
        yield runner
    finally:
        app.dependency_overrides.pop(get_cell_provisioner, None)


def _seed_org(db_session, *, suffix: str, role: str = "org_admin"):
    org = Org(id=f"org-{suffix}", name="Test Org")
    user = User(
        id=f"user-{suffix}",
        org_id=org.id,
        email=f"user-{suffix}@example.com",
        hashed_password="unused",
        role=role,
    )
    db_session.add_all([org, user])
    db_session.commit()
    return org, user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def _platform_admin_headers() -> dict[str, str]:
    token = create_access_token(user_id="platform-1", org_id=None, role="platform_admin")
    return {"Authorization": f"Bearer {token}"}


def test_org_admin_can_provision_their_own_cell(client, db_session, fake_provisioner):
    org, admin = _seed_org(db_session, suffix="p1")
    db_session.add(
        MailboxConnection(
            org_id=org.id,
            owner_user_id=admin.id,
            provider="gmail",
            email_address="a@example.com",
            refresh_token_encrypted=encrypt_token("refresh"),
        )
    )
    db_session.commit()

    resp = client.post("/api/v1/cells/mine/provision", headers=_headers(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["org_id"] == org.id
    assert body["status"] == "running"
    assert body["host_port"] == 41001

    assert fake_provisioner.calls[0][:2] == ["create", org.id]
    assert fake_provisioner.calls[1] == ["start", org.id]


def test_member_cannot_provision_a_cell(client, db_session, fake_provisioner):
    org, _admin = _seed_org(db_session, suffix="p2", role="org_admin")
    member = User(
        id="member-p2", org_id=org.id, email="m-p2@example.com", hashed_password="x", role="member"
    )
    db_session.add(member)
    db_session.commit()

    resp = client.post("/api/v1/cells/mine/provision", headers=_headers(member))
    assert resp.status_code == 403


def test_platform_admin_can_list_all_cells(client, db_session, fake_provisioner):
    org, admin = _seed_org(db_session, suffix="p3")
    db_session.add(
        MailboxConnection(
            org_id=org.id,
            owner_user_id=admin.id,
            provider="gmail",
            email_address="a@example.com",
            refresh_token_encrypted=encrypt_token("refresh"),
        )
    )
    db_session.commit()
    client.post("/api/v1/cells/mine/provision", headers=_headers(admin))

    resp = client.get("/api/v1/cells", headers=_platform_admin_headers())
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_org_admin_cannot_list_all_cells(client, db_session, fake_provisioner):
    org, admin = _seed_org(db_session, suffix="p4")
    resp = client.get("/api/v1/cells", headers=_headers(admin))
    assert resp.status_code == 403


def test_restart_failure_marks_cell_error(client, db_session):
    org, admin = _seed_org(db_session, suffix="p5")
    cell = AgentCell(org_id=org.id, tenant_key=org.id, status="running")
    db_session.add(cell)
    db_session.commit()

    runner = FakeFleetCliRunner()
    runner.queue("restart", FleetCliResult(returncode=1, stdout="", stderr="boom", json=None))
    provisioner = CellProvisioner(runner)
    app.dependency_overrides[get_cell_provisioner] = lambda: provisioner
    try:
        resp = client.post(f"/api/v1/cells/{org.id}/restart", headers=_platform_admin_headers())
    finally:
        app.dependency_overrides.pop(get_cell_provisioner, None)

    assert resp.status_code == 502
    db_session.refresh(cell)
    assert cell.status == "error"
