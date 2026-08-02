"""Seeds the single dev org/user used by the Phase 1 local vertical slice,
and prints a CELL_SERVICE_TOKEN for it.

The org id is fixed to "dev-org" (not a random uuid) for a stable, readable
dev identity. The printed CELL_SERVICE_TOKEN must be copied into `.env`
*before* the `openclaw` container starts — gmail-mcp/outlook-mcp require it
at process start (see agent-runtime/mcp-servers/*/src/config.ts) and use it
to authenticate to the token-broker/ingest endpoints; the control plane
derives which org a call is for from this token, not from a client-supplied
id (see core/security.py's create_cell_service_token).

Usage (after `alembic upgrade head` has created the schema):
    python -m app.scripts.seed_dev_org
"""

from app.core.security import Role, create_cell_service_token, hash_password
from app.db.session import SessionLocal
from app.models.org import Org
from app.models.user import User

DEV_ORG_ID = "dev-org"
DEV_ADMIN_EMAIL = "admin@dev.local"
DEV_ADMIN_PASSWORD = "devpassword123"  # noqa: S105 — dev-only seed, not a real credential


def main() -> None:
    db = SessionLocal()
    try:
        org = db.get(Org, DEV_ORG_ID)
        if org is None:
            org = Org(id=DEV_ORG_ID, name="Dev Org", plan_tier="trial", status="active")
            db.add(org)
            print(f"created org {DEV_ORG_ID}")
        else:
            print(f"org {DEV_ORG_ID} already exists")

        user = db.query(User).filter(User.email == DEV_ADMIN_EMAIL).one_or_none()
        if user is None:
            user = User(
                org_id=DEV_ORG_ID,
                email=DEV_ADMIN_EMAIL,
                hashed_password=hash_password(DEV_ADMIN_PASSWORD),
                role=Role.ORG_ADMIN.value,
            )
            db.add(user)
            print(f"created user {DEV_ADMIN_EMAIL} (password: {DEV_ADMIN_PASSWORD})")
        else:
            print(f"user {DEV_ADMIN_EMAIL} already exists")

        db.commit()

        token = create_cell_service_token(org_id=DEV_ORG_ID)
        print()
        print("Add this to .env, then (re)start the openclaw service:")
        print(f"CELL_SERVICE_TOKEN={token}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
