from app.core.metrics import agent_cells_by_status, refresh_cell_metrics
from app.models.agent_cell import AgentCell
from app.models.org import Org


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_pings_db(client):
    resp = client.get("/readyz")
    assert resp.status_code == 200


def test_metrics_endpoint_exposes_prometheus_format(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_requests_get_a_request_id_header(client):
    resp = client.get("/healthz")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) == 32  # uuid4().hex


def test_refresh_cell_metrics_reports_zero_for_absent_statuses(db_session):
    org = Org(id="org-metrics", name="Metrics Org")
    db_session.add(org)
    db_session.add(AgentCell(org_id=org.id, tenant_key=org.id, status="running"))
    db_session.commit()

    refresh_cell_metrics(db_session)

    assert agent_cells_by_status.labels(status="running")._value.get() == 1
    assert agent_cells_by_status.labels(status="error")._value.get() == 0
