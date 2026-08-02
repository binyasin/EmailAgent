from app.models.org import Org
from app.tests.conftest import cell_headers


def test_ingest_digest_stores_and_lists(client, db_session):
    org = Org(id="org-digest", name="Digest Org")
    db_session.add(org)
    db_session.commit()

    resp = client.post(
        "/internal/v1/digests/ingest",
        json={"period": "daily", "summary_text": "3 urgent threads, 2 drafts pending."},
        headers=cell_headers(org.id),
    )
    assert resp.status_code == 201
    assert resp.json()["period"] == "daily"

    from app.models.audit_log import AuditLog

    actions = [a.action for a in db_session.query(AuditLog).filter(AuditLog.org_id == org.id)]
    assert "digest.created" in actions


def test_ingest_digest_requires_a_cell_service_token(client, db_session):
    org = Org(id="org-digest-2", name="Digest Org 2")
    db_session.add(org)
    db_session.commit()

    resp = client.post(
        "/internal/v1/digests/ingest",
        json={"period": "daily", "summary_text": "irrelevant"},
        headers={"X-Cell-Service-Token": "not-a-real-token"},
    )
    assert resp.status_code == 401


def test_a_cells_token_cannot_ingest_a_digest_for_another_org(client, db_session):
    org_a = Org(id="org-digest-a", name="Org A")
    org_b = Org(id="org-digest-b", name="Org B")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    # org_a's cell token should only ever be able to write org_a's digests —
    # there's no tenant_id parameter left to spoof, but confirm a digest
    # posted with org_a's token lands under org_a, not wherever a caller
    # might wish it did.
    resp = client.post(
        "/internal/v1/digests/ingest",
        json={"period": "daily", "summary_text": "irrelevant"},
        headers=cell_headers(org_a.id),
    )
    assert resp.status_code == 201
    assert resp.json()["id"]

    from app.models.digest_run import DigestRun

    digest = db_session.get(DigestRun, resp.json()["id"])
    assert digest.org_id == org_a.id
