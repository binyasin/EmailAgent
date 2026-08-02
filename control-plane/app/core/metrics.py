"""Prometheus metrics. HTTP request metrics (latency/count/in-progress,
labeled by route+method+status — NOT by org_id) come from
prometheus-fastapi-instrumentator, wired in main.py. Custom business
metrics live here.

Cardinality warning: never add `org_id` (or any other unbounded, per-tenant
value) as a Prometheus label — with thousands of tenants that's thousands of
label combinations per metric, which is exactly the kind of cardinality
explosion that takes down a Prometheus instance. Per-org detail belongs in
the structured logs (see core/logging.py's request-context binding below),
which are fine at high cardinality; metrics stay aggregate-only.
"""

from prometheus_client import Gauge
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_cell import AgentCell

agent_cells_by_status = Gauge(
    "emailagent_agent_cells", "Number of provisioned agent cells, by status", ["status"]
)

# All possible AgentCell.status values, so a status that drops to zero still
# reports 0 instead of silently vanishing from the metric (a vanished series
# looks identical to "no data scraped yet" in Grafana, which is confusing
# during an incident — reporting 0 explicitly avoids that ambiguity).
_ALL_CELL_STATUSES = ["provisioning", "running", "stopped", "error", "deprovisioned"]


def refresh_cell_metrics(db: Session) -> None:
    counts = dict(
        db.execute(
            select(AgentCell.status, func.count()).group_by(AgentCell.status)
        ).all()
    )
    for status in _ALL_CELL_STATUSES:
        agent_cells_by_status.labels(status=status).set(counts.get(status, 0))
