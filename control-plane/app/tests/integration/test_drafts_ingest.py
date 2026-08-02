from app.models.mailbox_connection import MailboxConnection
from app.models.org import Org
from app.services.token_crypto import encrypt_token
from app.tests.conftest import cell_headers


def _seed_org_with_mailbox(db_session, *, suffix: str):
    org = Org(id=f"org-{suffix}", name="Test Org")
    mailbox = MailboxConnection(
        id=f"mb-{suffix}",
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
    resp = client.post(
        "/internal/v1/drafts/ingest",
        json={
            "mailbox_connection_id": "mb-x",
            "provider_draft_id": "pd-1",
            "thread_id": "t-1",
        },
    )
    assert resp.status_code == 401


def test_cell_can_ingest_a_draft_for_its_own_mailbox(client, db_session):
    org, mailbox = _seed_org_with_mailbox(db_session, suffix="own")

    resp = client.post(
        "/internal/v1/drafts/ingest",
        json={
            "mailbox_connection_id": mailbox.id,
            "provider_draft_id": "pd-1",
            "thread_id": "t-1",
            "subject": "Re: hello",
        },
        headers=cell_headers(org.id),
    )
    assert resp.status_code == 201
    assert resp.json()["mailbox_connection_id"] == mailbox.id


def test_a_cells_token_cannot_ingest_a_draft_for_another_orgs_mailbox(client, db_session):
    org_a, _mailbox_a = _seed_org_with_mailbox(db_session, suffix="a")
    _org_b, mailbox_b = _seed_org_with_mailbox(db_session, suffix="b")

    # org_a's cell token, but targeting org_b's mailbox_connection_id — this
    # is exactly the cross-tenant draft-injection vector the org_id check in
    # ingest_draft() closes.
    resp = client.post(
        "/internal/v1/drafts/ingest",
        json={
            "mailbox_connection_id": mailbox_b.id,
            "provider_draft_id": "pd-evil",
            "thread_id": "t-evil",
        },
        headers=cell_headers(org_a.id),
    )
    assert resp.status_code == 403

    from app.models.draft import Draft

    assert db_session.query(Draft).filter(Draft.provider_draft_id == "pd-evil").first() is None


def test_unknown_mailbox_connection_id_is_404(client, db_session):
    org, _mailbox = _seed_org_with_mailbox(db_session, suffix="unknown")

    resp = client.post(
        "/internal/v1/drafts/ingest",
        json={
            "mailbox_connection_id": "does-not-exist",
            "provider_draft_id": "pd-1",
            "thread_id": "t-1",
        },
        headers=cell_headers(org.id),
    )
    assert resp.status_code == 404
