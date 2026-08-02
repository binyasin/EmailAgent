from datetime import datetime, timedelta, timezone
from enum import StrEnum

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)

# bcrypt's algorithm itself ignores any password bytes past 72 — truncate
# explicitly rather than silently relying on that, so hash/verify agree
# regardless of library version behavior.
_BCRYPT_MAX_BYTES = 72


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"
    MEMBER = "member"


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(truncated, password_hash.encode("utf-8"))


def create_access_token(*, user_id: str, org_id: str | None, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {"sub": user_id, "org_id": org_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class CurrentUser:
    def __init__(self, user_id: str, org_id: str | None, role: Role):
        self.user_id = user_id
        self.org_id = org_id
        self.role = role


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    settings = get_settings()
    try:
        payload = jwt.decode(
            creds.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    return CurrentUser(
        user_id=payload["sub"], org_id=payload.get("org_id"), role=Role(payload["role"])
    )


def require_role(*roles: Role):
    def _dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles and user.role != Role.PLATFORM_ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return _dependency


def require_org_scope(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Every org-scoped route depends on this: org_id always comes from the
    verified JWT claim, never from a client-supplied path/query param."""
    if user.role != Role.PLATFORM_ADMIN and user.org_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no org")
    return user


def require_org_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """For org-scoped write routes (skill settings, VIP rules, invites):
    requires org_admin (or platform_admin) *and* a non-null org_id, since a
    platform_admin has no org of their own and org-scoped writes need one to
    attach the row to — unlike require_org_scope, a platform_admin does not
    get a free pass here without an org context."""
    if user.role not in (Role.ORG_ADMIN, Role.PLATFORM_ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    if user.org_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no org")
    return user


# --- Cell-service tokens ---
#
# Authenticates an agent cell's MCP servers (gmail-mcp/outlook-mcp) calling
# the internal token-broker/ingest endpoints. Each cell gets its own token,
# minted at provisioning time (see workers/provision_cell.py) with the
# owning org_id baked into the claims — the org identity comes from the
# verified token, never from a client-supplied tenant_id/org_id parameter.
#
# This replaces an earlier design (a single global shared secret compared
# for every cell) that was a real cross-tenant vulnerability: any cell —
# or anyone who obtained that one secret — could pass any org_id and pull
# another tenant's Gmail/Outlook access token, or inject fake drafts into
# another tenant's approval inbox. Found and fixed in a security review
# pass before this ever ran in a real multi-tenant deployment.
#
# Uses the same JWT_SECRET_KEY as user-facing access tokens (simpler than
# managing a second signing key) but a distinct `aud` claim, so a cell
# token and a user access token can never be substituted for each other.
CELL_SERVICE_AUDIENCE = "cell-service"


def create_cell_service_token(*, org_id: str) -> str:
    settings = get_settings()
    payload = {"org_id": org_id, "aud": CELL_SERVICE_AUDIENCE}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_cell_service_token(token: str) -> str:
    """Returns the org_id bound to this token, or raises 401."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=CELL_SERVICE_AUDIENCE,
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid cell service token") from exc
    return payload["org_id"]
