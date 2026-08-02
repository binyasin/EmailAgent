from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit_event(
    db: Session,
    *,
    org_id: str,
    actor_type: str,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        log_metadata=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry
