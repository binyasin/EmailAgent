from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class OrgMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    created_at: datetime


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"  # "member" | "org_admin"


class InviteMemberResponse(BaseModel):
    """Dev-mode shortcut: returns a one-time temporary password for the
    org_admin to relay to the invitee out-of-band. A production deployment
    should replace this with an emailed invite-token + self-service
    password-set flow instead of round-tripping a plaintext password through
    the API response — flagged here rather than silently shipped as final."""

    user: OrgMemberOut
    temporary_password: str


class ChangeRoleRequest(BaseModel):
    role: str  # "member" | "org_admin"
