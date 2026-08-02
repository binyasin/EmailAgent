from unittest.mock import patch

from app.models.mailbox_connection import MailboxConnection
from app.models.org import Org
from app.services.token_crypto import encrypt_token
from app.tests.conftest import cell_headers


def _seed_org_with_gmail(db_session, *, suffix: str):
    org = Org(id=f"org-{suffix}", name="Test Org")
    mailbox = MailboxConnection(
        org_id=org.id,
        owner_user_id="user-x",
        provider="gmail",
        email_address=f"{suffix}@example.com",
        refresh_token_encrypted=encrypt_token("refresh-token"),
        status="connected",
    )
    db_session.add_all([org, mailbox])
    db_session.commit()
    return org, mailbox


def test_missing_token_is_rejected(client, db_session):
    resp = client.get("/internal/v1/tokens/current", params={"provider": "gmail"})
    assert resp.status_code == 401


def test_invalid_token_is_rejected(client, db_session):
    resp = client.get(
        "/internal/v1/tokens/current",
        params={"provider": "gmail"},
        headers={"X-Cell-Service-Token": "garbage"},
    )
    assert resp.status_code == 401


def test_cell_can_fetch_its_own_orgs_token(client, db_session):
    org, _mailbox = _seed_org_with_gmail(db_session, suffix="own")

    with patch(
        "app.api.internal.token_broker.GmailProvider.refresh_access_token",
        return_value="fresh-access-token",
    ):
        resp = client.get(
            "/internal/v1/tokens/current",
            params={"provider": "gmail"},
            headers=cell_headers(org.id),
        )

    assert resp.status_code == 200
    assert resp.json()["access_token"] == "fresh-access-token"
    assert resp.json()["email_address"] == "own@example.com"


def test_a_cells_token_cannot_fetch_another_orgs_token(client, db_session):
    org_a, _mailbox_a = _seed_org_with_gmail(db_session, suffix="a")
    org_b, _mailbox_b = _seed_org_with_gmail(db_session, suffix="b")

    # org_a's cell token authenticates org_a — the endpoint no longer takes
    # a tenant_id parameter at all, so there's nothing to spoof to reach
    # org_b's mailbox; confirm it only ever sees its own org's connection.
    with patch(
        "app.api.internal.token_broker.GmailProvider.refresh_access_token",
        return_value="fresh-access-token",
    ):
        resp = client.get(
            "/internal/v1/tokens/current",
            params={"provider": "gmail"},
            headers=cell_headers(org_a.id),
        )

    assert resp.status_code == 200
    assert resp.json()["email_address"] == "a@example.com"  # never org_b's


def test_no_connected_mailbox_for_provider_is_404(client, db_session):
    org = Org(id="org-noprovider", name="No Provider Org")
    db_session.add(org)
    db_session.commit()

    resp = client.get(
        "/internal/v1/tokens/current",
        params={"provider": "gmail"},
        headers=cell_headers(org.id),
    )
    assert resp.status_code == 404
