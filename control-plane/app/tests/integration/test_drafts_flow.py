import app.api.v1.drafts as drafts_module
from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.draft import Draft
from app.models.mailbox_connection import MailboxConnection
from app.models.org import Org
from app.models.user import User
from app.services.token_crypto import encrypt_token


class StubGmailProvider:
    """Replaces the real GmailProvider (which would hit Google's network
    APIs) so the approve/reject flow can be tested without external calls."""

    def refresh_access_token(self, connection):
        return "fake-access-token"

    def send_draft(self, connection, provider_draft_id):
        return "sent-message-id"


class FailingGmailProvider:
    def refresh_access_token(self, connection):
        return "fake-access-token"

    def send_draft(self, connection, provider_draft_id):
        raise RuntimeError("provider API unavailable")


def _seed_org_user_mailbox(db_session, *, suffix: str):
    org = Org(id=f"org-{suffix}", name="Test Org")
    user = User(
        id=f"user-{suffix}",
        org_id=org.id,
        email=f"user-{suffix}@example.com",
        hashed_password="unused-in-these-tests",
        role="org_admin",
    )
    mailbox = MailboxConnection(
        id=f"mb-{suffix}",
        org_id=org.id,
        owner_user_id=user.id,
        provider="gmail",
        email_address=user.email,
        refresh_token_encrypted=encrypt_token("refresh-token"),
    )
    db_session.add_all([org, user, mailbox])
    db_session.commit()
    return org, user, mailbox


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def test_approve_draft_sends_via_provider_and_marks_sent(client, db_session, monkeypatch):
    org, user, mailbox = _seed_org_user_mailbox(db_session, suffix="approve")
    draft = Draft(
        id="draft-approve",
        org_id=org.id,
        mailbox_connection_id=mailbox.id,
        provider_draft_id="provider-draft-1",
        thread_id="thread-1",
        subject="Re: hello",
        status="pending_review",
    )
    db_session.add(draft)
    db_session.commit()

    monkeypatch.setitem(drafts_module._PROVIDERS, "gmail", StubGmailProvider())

    resp = client.post(
        f"/api/v1/drafts/{draft.id}/approve", json={}, headers=_auth_headers(user)
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"

    audit_actions = [a.action for a in db_session.query(AuditLog).filter(AuditLog.org_id == org.id)]
    assert "draft.approved" in audit_actions


def test_approve_draft_keeps_reviewable_state_as_failed_on_provider_error(
    client, db_session, monkeypatch
):
    org, user, mailbox = _seed_org_user_mailbox(db_session, suffix="fail")
    draft = Draft(
        id="draft-fail",
        org_id=org.id,
        mailbox_connection_id=mailbox.id,
        provider_draft_id="provider-draft-2",
        thread_id="thread-2",
        subject="Re: hello",
        status="pending_review",
    )
    db_session.add(draft)
    db_session.commit()

    monkeypatch.setitem(drafts_module._PROVIDERS, "gmail", FailingGmailProvider())

    resp = client.post(f"/api/v1/drafts/{draft.id}/approve", json={}, headers=_auth_headers(user))

    assert resp.status_code == 502
    db_session.refresh(draft)
    assert draft.status == "failed"


def test_reject_draft_marks_rejected_without_calling_provider(client, db_session):
    org, user, mailbox = _seed_org_user_mailbox(db_session, suffix="reject")
    draft = Draft(
        id="draft-reject",
        org_id=org.id,
        mailbox_connection_id=mailbox.id,
        provider_draft_id="provider-draft-3",
        thread_id="thread-3",
        subject="Re: hello",
        status="pending_review",
    )
    db_session.add(draft)
    db_session.commit()

    resp = client.post(f"/api/v1/drafts/{draft.id}/reject", headers=_auth_headers(user))

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_cannot_approve_a_draft_belonging_to_another_org(client, db_session):
    org_a, user_a, mailbox_a = _seed_org_user_mailbox(db_session, suffix="a")
    org_b, _user_b, mailbox_b = _seed_org_user_mailbox(db_session, suffix="b")

    other_org_draft = Draft(
        id="draft-cross-org",
        org_id=org_b.id,
        mailbox_connection_id=mailbox_b.id,
        provider_draft_id="provider-draft-4",
        thread_id="thread-4",
        subject="Not yours",
        status="pending_review",
    )
    db_session.add(other_org_draft)
    db_session.commit()

    resp = client.post(
        f"/api/v1/drafts/{other_org_draft.id}/approve", json={}, headers=_auth_headers(user_a)
    )

    assert resp.status_code == 404
